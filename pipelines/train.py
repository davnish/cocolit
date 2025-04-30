from ultralytics import YOLO

# Load a model
model = YOLO("yolo11n.pt")


if __name__ == "__main__":
    # Train the model
    train_results = model.train(
        data="configs/train.yaml",  # path to dataset YAML
        epochs=1000,  # number of training epochs
        imgsz=640,  # training image size
        device='cpu',  # device to run on, i.e. device=0 or device=0,1,2,3 or device=cpu
        save = True,
        save_period = 100,
        project = "../models/v1",

        hsv_h=0.015,  # Hue augmentation (range: 0-1)
        hsv_s=0.7,    # Saturation augmentation (range: 0-1)
        hsv_v=0.4,    # Value augmentation (range: 0-1)
        degrees=90,
        scale=0.5,
        shear=5,
        translate=0.2,
        flipud=0.5,   # Vertical flip probability
        fliplr=0.5,   # Horizontal flip probability
        mosaic=0.2,  # Enable mosaic augmentation
        # cutmix=0.5,
        mixup=0.1,    # Mixup augmentation probability

    )

    model.export(format="onnx")
    path = model.export(format="torchscript")  # return path to exported model
    # 
    # path of the exported model is returned 