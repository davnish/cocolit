import os

# Creates dir
dir = [
    os.path.join('data', 'test_dataset', 'test', 'images'),
    os.path.join('data', 'test_dataset', 'test', 'labels'),
    os.path.join('data', 'test_dataset', 'train', 'images'),
    os.path.join('data', 'test_dataset', 'train', 'labels'),
    os.path.join('data', 'test_dataset', 'val', 'images'),
    os.path.join('data', 'test_dataset', 'val', 'labels'),
    os.path.join('src'),
    os.path.join('test', 'unit'),
    os.path.join('steps'),
    os.path.join('pipelines'),
    os.path.join('notebooks'),
]

for i in dir:
    os.makedirs(i, exist_ok = True)
    # os.makefile(os.path.join(i, '.gitkeep'), exist_ok = True)
    with open(os.path.join(i, '.gitkeep'), 'w') as f:
        pass





