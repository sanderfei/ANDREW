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