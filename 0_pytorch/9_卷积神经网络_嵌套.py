import torch
import torch.nn as nn
from torchvision import transforms
from torchvision import datasets
from torch.utils.data import DataLoader
import torch.nn.functional as F
import torch.optim as optim

# ==================== 网络结构对比 ====================
# CNN：传统的、按顺序堆叠的卷积神经网络结构，一层接一层（Conv → 激活 →（可选池化/下采样）→ Conv → … → Head 输出）
# 每一层通常只有一个主分支（单尺度），一路往下

# Inception Module：并行的、多分支的卷积神经网络结构，一个模块有多个并行分支
# GoogLeNet	首次提出Inception的网络（2014年ImageNet冠军）
# 同时使用1x1、3x3、5x5等不同尺寸的卷积核，捕获不同尺度的特征
# 最后将所有分支的输出在通道维度拼接

batch_size = 64
transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])  # 归一化,均值和方差

train_dataset = datasets.MNIST(root='../dataset/mnist/', train=True, download=True, transform=transform)
train_loader = DataLoader(train_dataset, shuffle=True, batch_size=batch_size)
test_dataset = datasets.MNIST(root='../dataset/mnist/', train=False, download=True, transform=transform)
test_loader = DataLoader(test_dataset, shuffle=False, batch_size=batch_size)


# design model using class
class InceptionA(nn.Module):
    """
    Inception模块：包含4个并行分支，捕获不同尺度的特征

    输入: (batch, in_channels, H, W)
    输出: (batch, 88, H, W)  # 88 = 16 + 24 + 24 + 24

    4个分支：
    1. 1x1卷积：捕获点特征
    2. 1x1→5x5卷积：捕获大范围特征
    3. 1x1→3x3→3x3卷积：捕获中等范围特征（两个3x3相当于5x5，但参数更少）
    4. 平均池化→1x1卷积：保留空间信息
    """
    def __init__(self, in_channels):
        super(InceptionA, self).__init__()

        # ========== 分支1：1x1卷积分支 ==========
        # 输入: (batch, in_channels, H, W)
        # 输出: (batch, 16, H, W)
        # 作用: 捕获点特征，降维
        self.branch1x1 = nn.Conv2d(in_channels, 16, kernel_size=1)

        # ========== 分支2：5x5卷积分支 ==========
        # 第1步：1x1卷积降维
        # 输入: (batch, in_channels, H, W) → 输出: (batch, 16, H, W)
        self.branch5x5_1 = nn.Conv2d(in_channels, 16, kernel_size=1)
        # ↑ kernel_size=1，不会改变空间尺寸，所以不需要padding

        # 第2步：5x5卷积提取特征
        # 输入: (batch, 16, H, W) → 输出: (batch, 24, H, W)
        # padding=2保证输出尺寸不变：H_out = H_in - 5 + 2*2 + 1 = H_in（上下左右各补2圈0）
        # 卷积核宽度为5，卷积后H-4，需要补2圈0
        self.branch5x5_2 = nn.Conv2d(16, 24, kernel_size=5, padding=2)

        # ========== 分支3：双层3x3卷积分支 ==========
        # 第1步：1x1卷积降维
        # 输入: (batch, in_channels, H, W) → 输出: (batch, 16, H, W)
        self.branch3x3_1 = nn.Conv2d(in_channels, 16, kernel_size=1)

        # 第2步：第1个3x3卷积
        # 输入: (batch, 16, H, W) → 输出: (batch, 24, H, W)
        # padding=1保证输出尺寸不变
        self.branch3x3_2 = nn.Conv2d(16, 24, kernel_size=3, padding=1)

        # 第3步：第2个3x3卷积
        # 输入: (batch, 24, H, W) → 输出: (batch, 24, H, W)
        # 两个3x3卷积的感受野 = 5x5，但参数量更少
        self.branch3x3_3 = nn.Conv2d(24, 24, kernel_size=3, padding=1)

        # ========== 分支4：池化分支 ==========
        # forward有池化操作，池化后接1x1卷积
        # 输入: (batch, in_channels, H, W) → 输出: (batch, 24, H, W)
        # 作用: 保留空间信息，增加特征多样性
        self.branch_pool = nn.Conv2d(in_channels, 24, kernel_size=1)

    def forward(self, x):
        """
        前向传播：4个分支并行计算，然后在通道维度拼接

        Args:
            x: 输入张量 (batch, in_channels, H, W)

        Returns:
            输出张量 (batch, 88, H, W)
        """
        # ========== 分支1：1x1卷积 ==========
        branch1x1 = self.branch1x1(x)  # (batch, 16, H, W)

        # ========== 分支2：1x1 → 5x5卷积 ==========
        branch5x5 = self.branch5x5_1(x)          # (batch, 16, H, W)
        branch5x5 = self.branch5x5_2(branch5x5)  # (batch, 24, H, W)

        # ========== 分支3：1x1 → 3x3 → 3x3卷积 ==========
        branch3x3 = self.branch3x3_1(x)          # (batch, 16, H, W)
        branch3x3 = self.branch3x3_2(branch3x3)  # (batch, 24, H, W)
        branch3x3 = self.branch3x3_3(branch3x3)  # (batch, 24, H, W)

        # ========== 分支4：平均池化 → 1x1卷积 ==========
        # 平均池化：kernel_size=3, stride=1, padding=1 保证输出尺寸不变
        # stride 滑动窗口每次移动的步数
        # stride=1: 每次移动1个像素（密集扫描）
        # stride=2: 每次移动2个像素（跳跃扫描，输出尺寸减半）
        branch_pool = F.avg_pool2d(x, kernel_size=3, stride=1, padding=1)  # (batch, in_channels, H, W)
        branch_pool = self.branch_pool(branch_pool)  # (batch, 24, H, W)

        # ========== 拼接4个分支 ==========
        # 在通道维度(dim=1)拼接：16 + 24 + 24 + 24 = 88
        outputs = [branch1x1, branch5x5, branch3x3, branch_pool]
        return torch.cat(outputs, dim=1)  # (batch, 88, H, W)


# ==================== 完整网络定义 ====================
class Net(nn.Module):
    """
    混合Inception模块的卷积神经网络

    网络结构：
    输入(1,28,28)
    → Conv1(10,24,24)
    → Pool(10,12,12)
    → Incep1(88,12,12)
    → Conv2(20,8,8)
    → Pool(20,4,4)
    → Incep2(88,4,4)
    → Flatten(1408)
    → FC(10)
    """
    def __init__(self):
        super(Net, self).__init__()

        # ========== 第1个卷积层 ==========
        # 输入: (batch, 1, 28, 28)  # MNIST灰度图
        # 输出: (batch, 10, 24, 24)  # 28 - 5 + 1 = 24
        # 通道: 1 → 10
        self.conv1 = nn.Conv2d(1, 10, kernel_size=5)

        # ========== 第2个卷积层 ==========
        # 输入: (batch, 88, 12, 12)  # 来自incep1的输出
        # 输出: (batch, 20, 8, 8)    # 12 - 5 + 1 = 8
        # 通道: 88 → 20
        self.conv2 = nn.Conv2d(88, 20, kernel_size=5)

        # ========== 第1个Inception模块 ==========
        # 输入: (batch, 10, 12, 12)  # 来自conv1+pool的输出
        # 输出: (batch, 88, 12, 12)  # 88 = 16+24+24+24
        self.incep1 = InceptionA(in_channels=10)#对应conv1 output 10

        # ========== 第2个Inception模块 ==========
        # 输入: (batch, 20, 4, 4)    # 来自conv2+pool的输出
        # 输出: (batch, 88, 4, 4)    # 88 = 16+24+24+24
        self.incep2 = InceptionA(in_channels=20)#对应conv2 output 20

        # ========== 最大池化层 ==========
        # kernel_size=2, stride=2（默认）
        # 作用: 将特征图尺寸减半
        self.mp = nn.MaxPool2d(2)

        # ========== 全连接层 ==========
        # 输入: 1408 = 88 × 4 × 4
        # 输出: 10（数字0-9的类别数）
        self.fc = nn.Linear(1408, 10)

    def forward(self, x):
        """
        前向传播

        Args:
            x: 输入图片 (batch, 1, 28, 28)

        Returns:
            输出预测 (batch, 10)
        """
        in_size = x.size(0)  # 获取batch_size

        # ========== 第1阶段：Conv1 → Pool → ReLU ==========
        # (batch, 1, 28, 28) → (batch, 10, 24, 24) → (batch, 10, 12, 12)
        x = F.relu(self.mp(self.conv1(x)))

        # ========== 第2阶段：Inception1 ==========
        # (batch, 10, 12, 12) → (batch, 88, 12, 12)
        x = self.incep1(x)

        # ========== 第3阶段：Conv2 → Pool → ReLU ==========
        # (batch, 88, 12, 12) → (batch, 20, 8, 8) → (batch, 20, 4, 4)
        x = F.relu(self.mp(self.conv2(x)))

        # ========== 第4阶段：Inception2 ==========
        # (batch, 20, 4, 4) → (batch, 88, 4, 4)
        x = self.incep2(x)

        # ========== 第5阶段：Flatten ==========
        # (batch, 88, 4, 4) → (batch, 1408)
        # 1408 = 88 × 4 × 4
        x = x.view(in_size, -1)

        # ========== 第6阶段：全连接层 ==========
        # (batch, 1408) → (batch, 10)
        x = self.fc(x)

        return x


model = Net()

# construct loss and optimizer
criterion = torch.nn.CrossEntropyLoss()
optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.5)


# training cycle forward, backward, update


def train(epoch):
    running_loss = 0.0
    for batch_idx, data in enumerate(train_loader, 0):
        inputs, target = data
        optimizer.zero_grad()

        outputs = model(inputs)
        loss = criterion(outputs, target)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        if batch_idx % 300 == 299:
            print('[%d, %5d] loss: %.3f' % (epoch + 1, batch_idx + 1, running_loss / 300))
            running_loss = 0.0


def test():
    correct = 0
    total = 0
    with torch.no_grad():
        for data in test_loader:
            images, labels = data
            outputs = model(images)
            _, predicted = torch.max(outputs.data, dim=1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    print('accuracy on test set: %d %% ' % (100 * correct / total))


if __name__ == '__main__':
    for epoch in range(10):
        train(epoch)
        test()