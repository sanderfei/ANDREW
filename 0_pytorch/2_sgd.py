import matplotlib.pyplot as plt
#随机梯度下降

x_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
y_data = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0]

#init guess of weight
w = 1.0

def forward(x):
    return x * w

# 损失函数：单个样本的损失值
def loss(x,y):
    y_pred = forward(x)
    return (y_pred - y) ** 2

# 梯度：损失函数对权重的导数
def gradient(x,y):
    return 2 * x * (x * w - y)

epoch_list = []#迭代轮数
loss_list = []#
print("before training:", 4, forward(4))
for epoch in range(100):
    # 每轮每个样品都计算loss更新梯度
    for x,y in zip(x_data, y_data):
        grad = gradient(x,y)
        w -= 0.001 * grad # 每个样本都更新一次权重
        print("\tgrad:", x, y, grad)
        l = loss(x,y) # 每个样本都计算一次损失
    print("\tprogress:", epoch, ",w= ", w, "loss=", l)
    epoch_list.append(epoch)
    loss_list.append(l)

print("after training:", 4, forward(4))
plt.plot(epoch_list, loss_list)
plt.ylabel('loss')
plt.xlabel('epoch')
plt.show()