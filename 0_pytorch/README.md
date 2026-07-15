# PyTorch 基础学习总结

这个目录保存的是一组从数学公式逐步过渡到 PyTorch 神经网络的基础课件。重点不是训练出高精度模型，而是建立下面这条完整认知链：

```text
枚举参数观察损失
→ 手写梯度下降
→ PyTorch 自动求导
→ nn.Module + 优化器
→ 二分类与多分类
→ Dataset + DataLoader
→ CNN + GPU
→ Inception 多分支 + Residual 跳连接
```

对于 AI 应用开发工程师，这部分需要学到“能够读懂、调用和排查模型代码”的程度。后续使用 Embedding、Transformer 或大模型推理时，Tensor 形状、logits、batch、device 和推理模式仍然是共同基础。

## 学习顺序与文件索引

| 顺序 | 文件 | 核心知识点 |
| --- | --- | --- |
| 1 | [1_linear.py](1_linear.py) | 线性模型 `y_hat = wx`、平方误差、MSE、枚举参数观察损失曲线 |
| 2 | [1_linear_bias.py](1_linear_bias.py) | 增加偏置 `b`，观察 `w-b-MSE` 三维损失曲面 |
| 3 | [2_gd.py](2_gd.py) | 使用全部样本计算平均梯度，每轮更新一次参数 |
| 4 | [2_sgd.py](2_sgd.py) | 每个样本计算一次梯度并立即更新参数 |
| 5 | [3_back_propagation_反向传播.py](3_back_propagation_反向传播.py) | `requires_grad`、计算图、`backward()`、`grad` 和梯度累加 |
| 6 | [3_back_propagation_反向传播_pyTorch.py](3_back_propagation_反向传播_pyTorch.py) | 上一个自动求导示例的精简版本 |
| 7 | [3_back_propagation_反向传播_opt.py](3_back_propagation_反向传播_opt.py) | 二次函数拟合、向量化训练、`MSELoss`、Adam 优化器 |
| 8 | [4_pyTorch_Demo.py](4_pyTorch_Demo.py) | `nn.Module`、`nn.Linear`、`model.parameters()` 和标准训练循环 |
| 9 | [5_logistic.py](5_logistic.py) | 逻辑回归、Sigmoid、二分类概率和 `BCELoss` |
| 10 | [6_n_feature.py](6_n_feature.py) | 8 特征表格数据、三层 MLP、多特征二分类 |
| 11 | [7_CrossEntropy.py](7_CrossEntropy.py) | MNIST、DataLoader、mini-batch、全连接十分类、交叉熵 |
| 12 | [7_CrossEntropy_mydataset.py](7_CrossEntropy_mydataset.py) | 自定义 `Dataset`、`__len__`、`__getitem__` 和图片预处理 |
| 13 | [8_卷积神经网络.py](8_卷积神经网络.py) | `Conv2d`、池化、通道、特征图、基础 CNN |
| 14 | [8_卷积神经网络_GPU.py](8_卷积神经网络_GPU.py) | CPU/CUDA 设备选择以及模型、输入、标签的设备迁移 |
| 15 | [9_卷积神经网络_嵌套.py](9_卷积神经网络_嵌套.py) | 子模块注册、Inception 并行分支、不同感受野和通道拼接 |
| 16 | [9_卷积神经网络_跳连接.py](9_卷积神经网络_跳连接.py) | Residual Block、恒等映射和残差相加 |

[main.py](main.py) 只是 PyCharm 自动生成的 Hello World 模板，不属于 PyTorch 学习内容。

## 一、Tensor 与形状

Tensor 是 PyTorch 中承载数据、参数和梯度的核心对象。与普通 Python 列表相比，它支持：

- 多维数组运算；
- 自动求导；
- CPU、CUDA 等设备迁移；
- batch 并行计算。

本目录最重要的几种形状如下：

| 场景 | 输入形状 | 输出或标签形状 |
| --- | --- | --- |
| 单特征回归 | `[N, 1]` | `[N, 1]` |
| 8 特征二分类 | `[N, 8]` | 概率和标签均为 `[N, 1]` |
| MNIST 图片 | `[B, 1, 28, 28]` | logits 为 `[B, 10]` |
| MNIST 标签 | — | `[B]`，每个值是 `0～9` 的类别索引 |

常见维度含义：

```text
表格/全连接输入：[batch_size, feature_count]
图像输入：       [batch_size, channels, height, width]
分类输出：       [batch_size, class_count]
```

形状排查时优先打印：

```python
print(x.shape, x.dtype, x.device)
```

## 二、模型、预测与损失函数

### 1. 线性回归

最简单的线性模型是：

```text
y_hat = wx + b
```

平方误差和均方误差：

```text
loss_i = (y_hat_i - y_i)^2
MSE = (1 / N) * sum(loss_i)
```

`1_linear.py` 和 `1_linear_bias.py` 通过枚举参数寻找最低损失，帮助理解“训练的本质就是寻找让损失更小的参数”。

### 2. 二分类

`5_logistic.py` 和 `6_n_feature.py` 使用：

```text
Linear 输出 → Sigmoid → 0～1 概率 → BCELoss
```

Sigmoid 将任意实数压缩到 `(0, 1)`：

```text
sigmoid(z) = 1 / (1 + exp(-z))
```

当前代码使用 `Sigmoid + BCELoss`，便于观察概率。实际开发中更常见、更数值稳定的组合是：

```python
# forward 返回未经过 Sigmoid 的 logits
criterion = torch.nn.BCEWithLogitsLoss()
```

此时不要在模型末尾重复调用 Sigmoid。需要展示概率时，在推理阶段单独执行 `torch.sigmoid(logits)`。

### 3. 多分类

MNIST 是 10 分类任务。模型最后输出 `[B, 10]` 的原始分数 logits：

```python
logits = model(images)
loss = torch.nn.CrossEntropyLoss()(logits, labels)
prediction = logits.argmax(dim=1)
```

关键约定：

- `CrossEntropyLoss` 接收原始 logits，模型末尾不要手动添加 Softmax；
- `labels` 形状为 `[B]`，值是类别索引，不是 one-hot；
- MNIST 的标签类型通常为 `torch.int64`；
- `argmax(dim=1)` 表示在 10 个类别分数中选择最大值的索引。

`7_CrossEntropy.py` 使用的全连接网络形状为：

```text
[B, 1, 28, 28] → [B, 784] → [B, 512] → [B, 256]
→ [B, 128] → [B, 64] → [B, 10] logits
```

### 4. `sum` 与 `mean`

本目录同时出现了：

```python
torch.nn.MSELoss(reduction="sum")
torch.nn.BCELoss(reduction="sum")
torch.nn.BCELoss(reduction="mean")
```

- `sum`：累加 batch 内所有样本损失，batch 变大时数值通常也会变大；
- `mean`：取平均值，更容易在不同 batch size 之间比较。

比较不同实验的 loss 前，必须先确认使用的是哪种 reduction。

## 三、梯度下降与自动求导

线性模型 `y_hat = wx` 的 MSE 梯度为：

```text
dMSE/dw = (2 / N) * sum(x_i * (wx_i - y_i))
```

参数更新公式：

```text
w = w - learning_rate * gradient
```

### Batch GD、逐样本 SGD 与 mini-batch

| 方式 | 每次用多少数据计算梯度 | 当前示例 |
| --- | --- | --- |
| Batch GD | 全部样本 | `2_gd.py` |
| 逐样本更新 | 1 个样本 | `2_sgd.py` |
| Mini-batch SGD | 一小批样本 | MNIST 的 DataLoader 课件 |

`2_sgd.py` 没有随机打乱数据，因此严格说更接近固定顺序的逐样本更新。它记录的还是每轮最后一个样本的 loss，并不是整轮平均 MSE。

### Autograd 的完整过程

```python
w = torch.tensor([1.0], requires_grad=True)
loss = (x * w - y) ** 2  # 前向计算并建立计算图
loss.backward()          # 反向计算梯度
print(w.grad)            # 梯度保存在叶子张量的 grad 中
```

PyTorch 默认会累加梯度，所以每次参数更新前必须清零。使用优化器后的标准写法是：

```python
optimizer.zero_grad()
loss.backward()
optimizer.step()
```

早期课件通过 `w.data` 手动更新参数，这是为了展示原理。现代代码更推荐优化器；必须手动更新时，应使用 `torch.no_grad()`，避免绕过 Autograd 的安全检查：

```python
with torch.no_grad():
    w -= learning_rate * w.grad
w.grad.zero_()
```

本目录出现的优化器可以这样理解：

- SGD：直接沿当前梯度反方向更新参数；
- SGD + momentum：累计一段时间的更新方向，减少来回震荡；
- Adam：为不同参数维护自适应步长，二次函数拟合课件使用了它。

优化器只负责根据梯度更新参数，梯度本身仍由 `loss.backward()` 计算。

## 四、`nn.Module` 与标准训练闭环

继承 `nn.Module` 后，只要把层或子模块赋值给 `self.xxx`，PyTorch 就会自动注册其中的参数：

```python
class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = torch.nn.Linear(8, 1)

    def forward(self, x):
        return self.linear(x)
```

注册后的参数会自动出现在：

- `model.parameters()`；
- `model.state_dict()`；
- 优化器参数列表；
- `model.to(device)` 的递归迁移范围。

推荐记住下面这个标准模板：

```python
model.train()
for inputs, targets in train_loader:
    inputs = inputs.to(device)
    targets = targets.to(device)

    optimizer.zero_grad()
    outputs = model(inputs)
    loss = criterion(outputs, targets)
    loss.backward()
    optimizer.step()

model.eval()
with torch.no_grad():
    outputs = model(test_inputs.to(device))
```

其中：

- `model.train()` 开启训练模式；
- `model.eval()` 开启评估模式，会影响 Dropout、BatchNorm 等层；
- `torch.no_grad()` 关闭梯度记录，减少推理时的内存和计算；
- `loss.item()` 将单元素 Tensor 转成 Python 数值。

## 五、Dataset 与 DataLoader

`Dataset` 负责定义“一个样本怎么获取”，`DataLoader` 负责：

- 组合 batch；
- 打乱训练数据；
- 迭代整个数据集；
- 在需要时并行加载数据。

自定义 Dataset 的最小契约：

```python
class MyDataset(torch.utils.data.Dataset):
    def __len__(self):
        return sample_count

    def __getitem__(self, index):
        return input_tensor, label
```

`7_CrossEntropy_mydataset.py` 按 `标签_编号.png` 的文件名解析数字标签，再依次执行灰度转换、缩放、Tensor 转换和归一化。

`diabetes.csv` 包含 768 条样本、8 个输入特征和 1 个二分类标签。`6_n_feature.py` 的数据与网络形状为：

```text
X: [768, 8]
→ Linear(8, 6) + Sigmoid
→ Linear(6, 4) + Sigmoid
→ Linear(4, 1) + Sigmoid
→ probability: [768, 1]
```

训练集通常使用 `shuffle=True`，测试集通常使用 `shuffle=False`。最后一个 batch 可能小于设定的 `batch_size`，所以不要把 batch 数量硬编码为 64。

## 六、CNN 核心概念

### 1. 卷积、通道与空间尺寸

图像卷积输入采用 `[B, C, H, W]`。在 dilation 为 1 时，单个空间维度的输出大小为：

```text
output = floor((input + 2 * padding - kernel_size) / stride) + 1
```

基础 CNN 的形状变化：

```text
[B, 1, 28, 28]
→ Conv2d(1, 10, 5)  → [B, 10, 24, 24]
→ MaxPool2d(2)       → [B, 10, 12, 12]
→ Conv2d(10, 20, 5) → [B, 20, 8, 8]
→ MaxPool2d(2)       → [B, 20, 4, 4]
→ Flatten            → [B, 320]
→ Linear(320, 10)    → [B, 10]
```

核心规律：

- 卷积核在局部区域共享参数，提取空间特征；
- 网络加深时，通道数通常增加，空间尺寸通常减小；
- 池化降低空间尺寸和计算量；
- `view(batch_size, -1)` 或 `flatten` 把特征图转换成全连接层输入；
- 修改输入图片大小、卷积 padding 或池化后，必须重新计算全连接层输入维度。

### 2. CPU 与 CUDA

GPU 版本展示了最小设备选择逻辑：

```python
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)
inputs = inputs.to(device)
targets = targets.to(device)
```

模型、输入和标签必须位于同一设备，否则会出现 device mismatch。`loss.item()` 会把单个损失值转换成 CPU 上的 Python 数值。

### 3. Inception 与 Residual

| 结构 | 核心操作 | 形状要求 | 输出通道 |
| --- | --- | --- | --- |
| Inception | `torch.cat(branches, dim=1)` | 各分支的高和宽相同 | 各分支通道数之和 |
| Residual | `F(x) + x` | 两边全部维度相同，或先用投影对齐 | 通常保持目标通道数 |

Inception 示例包含四个并行分支：

```text
1x1 Conv                         → 16 通道
1x1 Conv → 5x5 Conv             → 24 通道
1x1 Conv → 3x3 Conv → 3x3 Conv → 24 通道
3x3 AvgPool → 1x1 Conv          → 24 通道
cat(dim=1)                       → 88 通道
```

`padding` 保证各分支空间尺寸一致，才能在通道维拼接。两个 `3x3` 卷积可以获得约等于一个 `5x5` 卷积的感受野；标准实现通常会在卷积之间加入激活以增加非线性，而当前课件没有加入这些激活，属于结构演示版。

残差块的核心形式为：

```text
y = ReLU(F(x) + x)
```

恒等分支给梯度提供了更直接的传播路径。课件注释里的“求导加 1，所以不会梯度消失”是便于入门的简化说法；严格来说，残差连接能缓解深层网络优化困难，但不能保证永远没有梯度问题。尺寸或通道不同时，也可以用 stride 和 `1x1` 卷积投影对齐，并非所有残差块都禁止池化或降采样。

## 七、当前代码中的重要注意事项

这些脚本保留了之前学习时的原始写法。阅读时应区分“用于解释原理的代码”和“现在推荐的工程写法”。

1. [1_linear.py](1_linear.py) 当前写成了 `import plt`，正常环境中应为 `import matplotlib.pyplot as plt`，因此它目前不能直接运行。
2. [1_linear_bias.py](1_linear_bias.py) 依赖 Visdom，并要求先启动 `python -m visdom.server`。
3. [3_back_propagation_反向传播_opt.py](3_back_propagation_反向传播_opt.py) 顶部注释仍写 `y=2x`，但实际代码拟合的是 `y=0.5x²+2x+1`，应以代码为准。
4. [6_n_feature.py](6_n_feature.py) 实际是多特征非线性二分类，不是注释所说的线性回归；它必须在本目录执行，才能读取相对路径 `diabetes.csv`。
5. `6_n_feature.py` 没有拆分训练集和测试集，也没有做特征缩放，因此只能用于理解网络结构，不能用训练 loss 证明泛化效果。
6. [7_CrossEntropy_mydataset.py](7_CrossEntropy_mydataset.py) 只演示数据加载，没有模型和交叉熵训练；当前目录也没有 `my_digits/train`、`my_digits/test`，直接运行会报目录不存在。
7. MNIST 课件首次运行会下载数据到 `../dataset/mnist/`，而且路径相对于启动命令所在目录，不是相对于 Python 文件。
8. 多个旧脚本使用 `.data` 读取或修改 Tensor。现代推理应使用 `torch.no_grad()`，预测类别可直接使用 `outputs.argmax(dim=1)`。
9. 多数分类脚本没有显式调用 `model.train()` 和 `model.eval()`。当前模型没有 Dropout/BatchNorm 时影响不明显，但工程代码应保留模式切换。
10. 残差网络脚本虽然创建了测试集，却没有执行测试准确率统计。
11. `Normalize((0.1307,), (0.3081,))` 的第二个参数是标准差，不是方差。
12. 课件没有固定随机种子，因此不同运行之间的初始参数、loss 和准确率可能不同。

## 八、运行说明

从仓库根目录进入本目录后运行，避免相对路径错位：

```bash
cd /home/wangfei/code/andrew/0_pytorch
```

从 Windows 项目复制时没有带入 `.venv`。请使用当前仓库的 Python 环境，并根据机器的 CPU/CUDA 情况通过 [PyTorch 官方安装选择器](https://pytorch.org/get-started/locally/) 安装 `torch` 和 `torchvision`。其他脚本依赖包括：

```bash
python -m pip install numpy matplotlib pillow

# 只有 1_linear_bias.py 需要
python -m pip install visdom
```

建议先从不需要数据集下载的脚本开始：

```bash
python 2_gd.py
python 3_back_propagation_反向传播_opt.py
python 4_pyTorch_Demo.py
python 5_logistic.py
python 6_n_feature.py
```

MNIST 和 CNN 脚本首次运行需要网络，默认完整训练 10 个 epoch，CPU 环境下会明显慢于前面的数学示例。

## 九、学完后的完成标准

学完这个目录后，应该能够独立回答和完成：

- 解释 Tensor 的 shape、dtype 和 device；
- 解释前向传播、损失函数、反向传播和参数更新的关系；
- 说明梯度为什么要清零，以及学习率过大或过小的影响；
- 写出一个最小 `nn.Module` 和标准训练循环；
- 区分回归、二分类和多分类所需的输出与损失函数；
- 解释 `Dataset` 与 `DataLoader` 的职责；
- 追踪 MLP/CNN 每一层的输入输出形状；
- 让模型和输入正确运行在同一设备；
- 说明 Inception 的通道拼接与 Residual 的逐元素相加有什么不同；
- 在推理阶段正确使用 `model.eval()` 和 `torch.no_grad()`。

对于 AI 应用开发岗位，完成以上内容后即可进入 Hugging Face Transformers、Embedding 模型调用、批量推理、模型保存加载和简单推理服务，不需要在这里继续深挖手写 CNN 训练技巧。
