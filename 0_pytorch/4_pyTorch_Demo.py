import torch

# 训练数据：输入x和对应的输出y（关系是 y = 2x）
# torch.Tensor 创建张量
# [[1.0]] 是二维张量，shape=(3,1)，类似 [][]float64
#  张量是PyTorch/TensorFlow等深度学习框架的核心数据结构，比普通数组多了GPU支持和自动求导能力
x_data = torch.Tensor([[1.0], [2.0], [3.0]])
y_data = torch.Tensor([[2.0], [4.0], [6.0]])

# 定义线性模型类（继承自torch.nn.Module）
class LinearModel(torch.nn.Module):
    def __init__(self):
        # super() 调用父类构造函数
        super(LinearModel, self).__init__()
        # torch.nn.Linear(in_features, out_features) 创建线性层
        # 参数：输入维度=1，输出维度=1 代表一个输入一个输出
        # 内部包含权重w和偏置b，会自动初始化
        self.linear = torch.nn.Linear(1, 1)

    # forward 定义前向传播逻辑
    # 参数x：输入张量
    def forward(self, x):
        # 调用线性层计算：y = w*x + b
        y_pred = self.linear(x)
        return y_pred

# 实例化模型
model = LinearModel()

# 损失函数：均方误差MSE（Mean Squared Error）
# 计算公式：loss = Σ(y_pred - y_true)²
criterion = torch.nn.MSELoss(reduction='sum')

# 优化器：随机梯度下降SGD（Stochastic Gradient Descent）
# model.parameters() 获取模型所有可训练参数（w和b）
# lr=0.01 学习率（learning rate），控制参数更新步长
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

# 训练循环：迭代1000轮（epoch）
for epoch in range(1000):
    # 1. 前向传播：计算预测值
    y_pred = model(x_data)  # 等价于 model.forward(x_data)
    
    # 2. 计算损失
    loss = criterion(y_pred, y_data)
    print(f"Epoch: {epoch} | Loss: {loss.item()}")  # .item() 将张量转为Python数值
    
    # 3. 反向传播三步骤：
    optimizer.zero_grad()  # 清空上一轮的梯度（必须！否则梯度会累加）
    loss.backward()        # 自动计算梯度 ∂loss/∂w 和 ∂loss/∂b
    optimizer.step()       # 更新参数：w = w - lr*grad_w, b = b - lr*grad_b

# 训练完成，查看学到的参数
# model.linear.weight 是权重w（张量）
# model.linear.bias 是偏置b（张量）
# .item() 转为Python标量
print("w = ", model.linear.weight.item())
print("b = ", model.linear.bias.item())

# 测试：用训练好的模型预测新数据
x_test = torch.Tensor([[4.0]])
y_test = model(x_test)  # 前向传播
print("y_pred = ", y_test.data.item())  # .data 访问张量数据（不记录梯度）
