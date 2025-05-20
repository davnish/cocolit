import os
import random
from pathlib import Path

random.seed(42)


def shuffle_data(data_list: list) -> list:
    random.shuffle(data_list)
    return data_list


def train_test_split(images: str, labels: str, train_ratio: float):
    """This split the dataset whcih consist of data and label into training and testing set.
        Note: This wont work if there are mutiple directories inside data_path or label_path
    Args:
        images (str): Path consisting the data.
        labels (str): Path consisting the labels.
        train_ratio (float): Ratio of the train_size. Range from 0 - 1.


    Returns:
        list (str): training_data, training_label, testing_data, testing_label.
    """

    images = Path(images)
    labels = Path(labels)

    img_list = [i for i in images.glob("*.tif")]

    label_list = [labels / (i.stem + ".txt") for i in img_list]

    img_list = shuffle_data(img_list)

    train_size = int(len(img_list) * train_ratio)

    trainx = img_list[:train_size]
    trainy = label_list[:train_size]
    testx = img_list[train_size:]
    testy = label_list[train_size:]

    print(f"Train Size: {train_size}, Test Size: {len(img_list) - train_size}")
    return trainx, trainy, testx, testy
