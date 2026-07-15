import torch

# 数据：你原来的 y = 2x（用二次模型也能学到 a≈0, b≈2, c≈0）
x_data = torch.tensor([1.,2.,3.,4.,5.,6.,7.,8.,9.])
y_data = 0.5 * x_data**2 + 2 * x_data + 1

# 参数 a, b, c
a = torch.tensor([0.1], requires_grad=True)
b = torch.tensor([1.0], requires_grad=True)
c = torch.tensor([2.0], requires_grad=True)

def forward(x):
    return a * x**2 + b * x + c

criterion = torch.nn.MSELoss()
# optimizer = torch.optim.SGD([a, b, c], lr=1e-5)
optimizer = torch.optim.Adam([a, b, c], lr=0.01)


print("before training:", 4.0, forward(torch.tensor(4.0)).item())

for epoch in range(5000):  # ⬅️ 只需 5000 轮
    # 1) 前向
    y_pred = forward(x_data)

    # 2) 损失（均方误差）
    loss = criterion(y_pred, y_data)

    # 3) 反向：先清梯度，再 backward 计算梯度
    optimizer.zero_grad()
    loss.backward()

    # 4) 更新梯度
    optimizer.step()

    if (epoch + 1) % 100 == 0:
        print(f"epoch {epoch+1:4d} | loss={loss.item():.6f} | a={a.item():.6f} b={b.item():.6f} c={c.item():.6f}")

print("after training:", 4.0, forward(torch.tensor(4.0)).item())
print(f"理论值: a=0.5, b=2.0, c=1.0")
print(f"训练值: a={a.item():.4f}, b={b.item():.4f}, c={c.item():.4f}")
