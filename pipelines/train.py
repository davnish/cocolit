from ultralytics import YOLO

# Load a model
model = YOLO("yolo11s.pt")


if __name__ == "__main__":
    # Train the model
    train_results = model.train(
        data="../configs/train.yaml",  # path to dataset YAML
        epochs=1000,  # number of training epochs
        imgsz=640,  # training image size
        device='cpu',  # device to run on, i.e. device=0 or device=0,1,2,3 or device=cpu
        # save_period = 100,  # directory to save results
        # save_best = True,  # save the best model
        # workers = 2
        save = True,
        save_period = 100,
        project = "../models/v1",

    )


    path = model.export(format="torchscript")  # return path to exported model
    # 
    # path of the exported model is returned 