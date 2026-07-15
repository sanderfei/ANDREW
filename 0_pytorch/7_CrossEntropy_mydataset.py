import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
import os


# ==================== 自定义数据集类 ====================
class CustomDigitDataset(Dataset):
    """
    自定义手写数字数据集

    目录结构：
    my_digits/
    ├── train/
    │   ├── 0_001.png  # 文件名格式：标签_编号.png
    │   ├── 0_002.png
    │   ├── 1_001.png
    │   ├── 1_002.png
    │   └── ...
    └── test/
        ├── 0_001.png
        └── ...
    """

    def __init__(self, image_dir, transform=None):
        """
        Args:
            image_dir: 图片目录路径
            transform: 数据预处理
        """
        self.image_dir = image_dir
        self.transform = transform

        # 获取所有图片文件
        self.image_files = []
        self.labels = []

        for filename in os.listdir(image_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                # 从文件名提取标签（假设格式：标签_编号.png）
                label = int(filename.split('_')[0])
                self.image_files.append(filename)
                self.labels.append(label) #关键：把图片和对应的目的数字标签对应

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        # 加载图片
        img_path = os.path.join(self.image_dir, self.image_files[idx])
        image = Image.open(img_path).convert('L')  # 转为灰度图

        # 获取标签
        label = self.labels[idx]

        # 应用预处理
        if self.transform:
            image = self.transform(image)

        return image, label


# ==================== 数据预处理 ====================
transform = transforms.Compose([
    transforms.Resize((28, 28)),  # 调整为28x28
    transforms.ToTensor(),  # 转为Tensor
    transforms.Normalize((0.5,), (0.5,))  # 归一化
])

# ==================== 加载自定义数据集 ====================
batch_size = 64

# 训练集
train_dataset = CustomDigitDataset(
    image_dir='my_digits/train/',
    transform=transform
)

train_loader = DataLoader(
    train_dataset,
    batch_size=batch_size,
    shuffle=True
)

# 测试集
test_dataset = CustomDigitDataset(
    image_dir='my_digits/test/',
    transform=transform
)

test_loader = DataLoader(
    test_dataset,
    batch_size=batch_size,
    shuffle=False
)

print(f"训练集大小: {len(train_dataset)}")
print(f"测试集大小: {len(test_dataset)}")