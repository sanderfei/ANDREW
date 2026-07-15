import numpy as np
import plt

x_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
y_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]

# 前向传播，预测函数
def forward(x):
    return x * w

# 损失： 单个样本的损失值，使用均方误差
def loss(x, y):
    return (forward(x) - y) ** 2

w_list = []
mse_list = []
for w  in np.arange(0.0, 2.1, 0.1):
    print("w=", w)
    loss_sum = 0
    for x_val, y_val in zip(x_data, y_data):
        y_pred_val = forward(x_val)
        loss_val = loss(x_val, y_val)
        loss_sum += loss_val
        print('\t', x_val, y_val,y_pred_val,loss_val)
    mse = loss_sum / len(x_data)
    print("MSE:", mse) # MSE（所有样本损失的平均值） = Σ(loss) / n
    w_list.append(w)
    mse_list.append(mse)

plt.plot(w_list, mse_list)
plt.ylabel('LOSS')
plt.xlabel('W')
plt.show()


# 均方误差数学表达式
# cost = (1/N) × Σ(ŷₙ - yₙ)²
#        └─┬─┘   └────┬────┘
#       平均值    预测误差的平方和

