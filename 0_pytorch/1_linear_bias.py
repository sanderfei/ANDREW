import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from visdom import Visdom

# 初始化 Visdom
viz = Visdom()
assert viz.check_connection(), "Visdom服务器未启动！请先运行: python -m visdom.server"

# 训练数据：y = x + 1 的线性关系
x_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
y_data = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

# 前向传播：计算预测值
def forward(x, w, b):
    return x * w + b

# 损失函数：计算均方误差
def loss(x, y, w, b):
    return (forward(x, w, b) - y) ** 2

# 存储参数和损失
w_list = []
b_list = []
mse_list = []

# 遍历不同的 w 和 b 值
for w in np.arange(0.0, 2.1, 0.1):
    for b in np.arange(0.0, 2.1, 0.1):
        l_sum = 0
        # 计算所有样本的总损失
        for x_val, y_val in zip(x_data, y_data):
            loss_val = loss(x_val, y_val, w, b)
            l_sum += loss_val

        # 计算平均损失
        mse = l_sum / len(x_data)
        w_list.append(w)
        b_list.append(b)
        mse_list.append(mse)

# Visdom 3D 散点图
viz.scatter(
    X=np.column_stack([w_list, b_list, mse_list]),
    opts=dict(
        title='Parameter Space: W-B-MSE',
        xlabel='Weight (W)',
        ylabel='Bias (B)',
        zlabel='MSE Loss',
        markersize=3,
        markercolor=np.array(mse_list),
    )
)

# 找到最优参数
min_idx = np.argmin(mse_list)
best_w, best_b, min_mse = w_list[min_idx], b_list[min_idx], mse_list[min_idx]

# Visdom 文本显示
viz.text(f"最优参数: w={best_w:.2f}, b={best_b:.2f}, MSE={min_mse:.6f}", 
         opts=dict(title='优化结果'))

# 3D可视化：w-b-MSE 关系
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')  # 创建3D坐标系
ax.scatter(w_list, b_list, mse_list, c=mse_list, cmap='viridis')
ax.set_xlabel('Weight (W)')
ax.set_ylabel('Bias (B)')
ax.set_zlabel('MSE Loss')
plt.title('Parameter Space: W-B-MSE')
plt.show()

