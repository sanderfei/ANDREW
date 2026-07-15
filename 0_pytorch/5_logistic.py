import torch

# 二分类示例：根据学习时长预测是否通过考试
x_data = torch.Tensor([[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]])
y_data = torch.Tensor([[0.0], [0.0], [0.0], [1.0], [1.0], [1.0]])  # 0=不通过, 1=通过


class LogisticModel(torch.nn.Module):
    def __init__(self):
        super(LogisticModel, self).__init__()
        self.linear = torch.nn.Linear(1, 1)

    def forward(self, x):
        # Sigmoid函数 - 将任意值压缩到(0,1)：
        y_pred = torch.sigmoid(self.linear(x))
        return y_pred

model = LogisticModel()
# 二分类损失函数
criterion = torch.nn.BCELoss(reduction='sum')
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

for epoch in range(1000):
    y_pred = model(x_data)
    loss = criterion(y_pred, y_data)
    print(f"Epoch: {epoch} | Loss: {loss.item()}")

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

x_test = torch.Tensor([[7.0]])
y_test = model(x_test)
print("y_pred = ", y_test.data.item())