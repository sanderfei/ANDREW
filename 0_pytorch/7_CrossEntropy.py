import torch
from torchvision import transforms
from torchvision import datasets
from torch.utils.data import DataLoader
import torch.nn.functional as F
import torch.optim as optim

# ==================== 交叉熵损失 - MNIST手写数字识别 ====================

# 批次大小：每次训练使用64张图片
batch_size = 64

# 数据预处理流程
transform = transforms.Compose([
    transforms.ToTensor(),                      # 1. PIL图片 → Tensor，像素值从[0,255] → [0,1]
    transforms.Normalize((0.1307,), (0.3081,))  # 2. 归一化：(x - 均值) / 标准差，使数据分布更稳定
])  # 0.1307和0.3081是MNIST数据集的统计值

# ==================== 加载MNIST数据集 ====================
# 训练集：60000张手写数字图片（0-9）
train_dataset = datasets.MNIST(
    root='../dataset/mnist/',  # 数据存储路径（自动下载）
    train=True,                # True=训练集，False=测试集
    download=True,             # 首次运行自动下载
    transform=transform        # 应用上面定义的预处理
)

# 训练数据加载器：将数据分批次加载
train_loader = DataLoader(
    train_dataset, 
    shuffle=True,              # 每个epoch打乱数据顺序（防止过拟合）
    batch_size=batch_size      # 每批64张图片
)

# 测试集：10000张图片
test_dataset = datasets.MNIST(
    root='../dataset/mnist/', 
    train=False,               # 测试集
    download=True, 
    transform=transform
)

# 测试数据加载器
test_loader = DataLoader(
    test_dataset, 
    shuffle=False,             # 测试时不需要打乱
    batch_size=batch_size
)


# ==================== 定义神经网络模型 ====================
class Net(torch.nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        # 5层全连接网络：784 → 512 → 256 → 128 → 64 → 10
        # 784 = 28 * 28，即MNIST图片的像素总数
        # 10 = 0-9十个数字类别
        # 全连接网络（Fully Connected Network）= 每个神经元都与上一层的所有神经元相连。
        self.l1 = torch.nn.Linear(784, 512)   # 输入层：28*28=784像素 → 512个神经元
        self.l2 = torch.nn.Linear(512, 256)   # 隐藏层1：512 → 256
        self.l3 = torch.nn.Linear(256, 128)   # 隐藏层2：256 → 128
        self.l4 = torch.nn.Linear(128, 64)    # 隐藏层3：128 → 64
        self.l5 = torch.nn.Linear(64, 10)     # 输出层：64 → 10（对应0-9十个数字）

    def forward(self, x):
        # x原始形状：(batch_size, 1, 28, 28) = (64, 1, 28, 28)
        x = x.view(-1, 784)  # 展平为一维：(64, 784)，-1表示自动计算batch_size

        # 原始：64张28×28的图片
        # [
        #     [[像素1, 像素2, ..., 像素28],  # 第1行
        #      [像素29, 像素30, ..., 像素56],  # 第2行
        #      ...
        #      [像素757, ..., 像素784]],  # 第28行
        #
        #     [[第2张图片...]],
        #     ...
        #     [[第64张图片...]]
        # ]

        # ↓ view(-1, 784) 展平

        # 新形状：64行，每行784个像素
        # [
        #     [像素1, 像素2, 像素3, ..., 像素784],  # 第1张图片
        #     [像素1, 像素2, 像素3, ..., 像素784],  # 第2张图片
        #     ...
        #     [像素1, 像素2, 像素3, ..., 像素784]  # 第64张图片
        # ]

        # 前4层使用ReLU激活函数（引入非线性）# 可以学习复杂模式（如曲线、边界）
        x = F.relu(self.l1(x))  # (64, 784) → (64, 512) 将784维输入转换为512维输出
        x = F.relu(self.l2(x))  # (64, 512) → (64, 256)
        x = F.relu(self.l3(x))  # (64, 256) → (64, 128)
        x = F.relu(self.l4(x))  # (64, 128) → (64, 64)
        
        # 最后一层不做激活，直接输出原始分数（logits）
        # CrossEntropyLoss内部会自动应用Softmax
        # Softmax: 一组任意实数分数（logits）转换成概率分布的函数
        # Softmax(x_i) = exp(x_i) / Σ exp(x_j)
        #              ↑          ↑
        #              分子        分母（所有类别的exp之和）

        # 例如：logits = [2.0, 1.0, 0.1]
        #
        # 分子：
        # exp(2.0) = 7.389
        # exp(1.0) = 2.718
        # exp(0.1) = 1.105
        #
        # 分母：
        # Σ = 7.389 + 2.718 + 1.105 = 11.212
        #
        # 概率：
        # P(类别0) = 7.389 / 11.212 = 0.659 (65.9%)
        # P(类别1) = 2.718 / 11.212 = 0.242 (24.2%)
        # P(类别2) = 1.105 / 11.212 = 0.099 (9.9%)
        return self.l5(x)  # (64, 64) → (64, 10)


# 实例化模型
model = Net()

# ==================== 定义损失函数和优化器 ====================
# 交叉熵损失：适用于多分类问题（10个类别：0-9）
# 内部会自动对输出应用Softmax，然后计算交叉熵(预测越接近真实标签，交叉熵越小)
criterion = torch.nn.CrossEntropyLoss()

# SGD优化器：随机梯度下降
optimizer = optim.SGD(
    model.parameters(),  # 模型的所有可训练参数
    lr=0.01,            # 学习率：控制参数更新步长
    momentum=0.5        # 动量：加速收敛，减少震荡
)


# ==================== 训练函数 ====================
def train(epoch):
    running_loss = 0.0  # 累计损失
    
    # enumerate(train_loader, 0)：遍历所有批次，从索引0开始
    for batch_idx, data in enumerate(train_loader, 0):
        # 1. 获取一个批次的数据
        inputs, target = data  # inputs: (64, 1, 28, 28), target: (64,)
        # inputs: torch.Size([64, 1, 28, 28]) - 64张图片
                    #         ↑   ↑  ↑   ↑
                    #         |   |  |   └─ 宽度28像素
                    #         |   |  └───── 高度28像素
                    #         |   └──────── 1个通道（灰度图）
                    #         └──────────── 批次大小64
        # target: torch.Size([64]) - 64个标签
        #         例如：tensor([5, 0, 4, 1, 9, 2, ...])
        #         表示第1张图是数字5，第2张是0，第3张是4...
        
        # 2. 清空上一轮的梯度（必须！）
        optimizer.zero_grad()
        
        # 3. 前向传播：计算预测值
        outputs = model(inputs)  # (64, 10) - 每张图片对应10个分数
        
        # 4. 计算损失
        # outputs: (64, 10) - 模型输出的原始分数
        # target: (64,) - 真实标签，如 [5, 0, 4, 1, ...]
        loss = criterion(outputs, target)
        
        # 5. 反向传播：计算梯度
        loss.backward()
        
        # 6. 更新参数：w = w - lr * grad
        optimizer.step()

        # 7. 累计损失（用于打印）
        running_loss += loss.item()
        
        # 每300个批次打印一次平均损失
        if batch_idx % 300 == 299:
            print('[%d, %5d] loss: %.3f' % (epoch + 1, batch_idx + 1, running_loss / 300))
            running_loss = 0.0  # 重置累计损失


# ==================== 测试函数 ====================
def test():
    correct = 0  # 预测正确的数量
    total = 0    # 总样本数
    
    # torch.no_grad()：测试时不需要计算梯度（节省内存，加速）
    with torch.no_grad():
        for data in test_loader:
            images, labels = data  # images: (64, 1, 28, 28), labels: (64,)
            
            # 前向传播
            outputs = model(images)  # (64, 10)
            
            # torch.max(outputs.data, dim=1) 返回两个值：
            # - 第一个值：每行的最大值（不需要，用_接收）
            # - 第二个值：最大值的索引（即预测的数字）
            # dim=1 表示在第1维（列）上找最大值
            _, predicted = torch.max(outputs.data, dim=1)  # predicted: (64,)
            
            # 统计总数
            total += labels.size(0)  # labels.size(0) = 64
            
            # 统计正确数量
            # (predicted == labels) 返回布尔张量：[True, False, True, ...]
            # .sum() 统计True的数量
            # .item() 转为Python数值
            correct += (predicted == labels).sum().item()
    
    # 打印准确率
    print('accuracy on test set: %d %% ' % (100 * correct / total))


# ==================== 主程序 ====================
if __name__ == '__main__':
    # 训练10轮（epoch）
    for epoch in range(10):
        train(epoch)  # 训练一轮
        test()        # 测试当前模型性能
