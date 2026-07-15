import torch
#反向传播
#
x_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
y_data = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0]

w = torch.tensor([1.0]) #线性模型举例
w.requires_grad = True # 计算梯度

def forward(x):
    return x * w  #w是一个tensor

def loss(x,y):
    return (forward(x) - y) ** 2

print("before training:", 4, forward(4).item())

for epoch in range(100):
    for x,y in zip(x_data, y_data):
        l = loss(x,y) #l是一个张量 tensor主要是在建立计算图 forward
        l.backward()
        print("\tgrad:", x, y, w.grad.item()) #w.grad是一个张量
        w.data = w.data - 0.01 * w.grad.data #更新权重 注意grad 也是一个tensor
        w.grad.data.zero_() #清空梯度
    print("progress:", epoch, l.item())

print("after training:", 4, forward(4).item())

# --- 步骤1：前向传播 ---
# l = loss(x, y)
# l是Tensor，内部存储了计算图：
# l = (x*w - y)²
#      └─┬─┘
#    这个计算过程被记录下来

# --- 步骤2：反向传播（自动计算梯度）---
# l.backward()
# ⬅️ 核心！自动计算 ∂l/∂w
# PyTorch沿着计算图反向传播，计算梯度
# 结果存储在 w.grad 中

# --- 步骤3：查看梯度 ---
# print("\tgrad:", x, y, w.grad.item())
# w.grad 是Tensor，存储了梯度值
# .item() 转为数字打印

# --- 步骤4：更新参数 ---
# w.data = w.data - 0.01 * w.grad.data
# w.data：访问Tensor的原始数据（不记录梯度）
# 等价于：w = w - 0.01 * w.grad（但这样会创建新计算图）

# --- 步骤5：清空梯度 ---
# w.grad.data.zero_()
# ⬅️ 重要！必须清空，否则梯度会累加
# .zero_() 是就地操作（in-place），直接修改原数据
