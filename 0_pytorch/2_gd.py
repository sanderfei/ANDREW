import matplotlib.pyplot as plt
#梯度下降

x_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
y_data = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0]

#init guess of weight
w = 1.0

def forward(x):
    return x * w

# 损失函数：所有样本损失的平均值
def cost (xs, ys):
    cost = 0
    for x,y in zip(xs,ys):
        cost += (forward(x) -y) ** 2
    return cost / len(xs)

# 梯度：损失函数对权重的导数（所有样本的梯度的平均值）
def gradient(xs, ys):
    grad = 0
    for x,y in zip(xs, ys):
        grad += 2 * x * (forward(x) - y)
    return grad / len(xs)

epoch_list = []#迭代轮数
cost_list = []#每轮的平均损失（MSE均方误差）
print("before training:", 4, forward(4))
for epoch in range(100):
    cost_val = cost(x_data, y_data)
    grad_val = gradient(x_data, y_data)
    w -= 0.001 * grad_val
    print(f"epoch: {epoch} w={w:.4f} cost={cost_val:.4f}")
    epoch_list.append(epoch)
    cost_list.append(cost_val)
#如果算法正确，随着循环的迭代，那么w逐渐趋向于理论值

print("after training:", 4, forward(4))
plt.plot(epoch_list, cost_list)
plt.ylabel('cost')
plt.xlabel('epoch')
plt.show()
