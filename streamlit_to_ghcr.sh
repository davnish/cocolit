set -e

NAMESPACE=davnish
TAG=$(git rev-parse --short HEAD)
IMAGE_NAME=ghcr.io/$NAMESPACE/streamlit-server:$TAG


docker buildx build --platform linux/amd64 -t $IMAGE_NAME -f streamlit.Dockerfile .

# docker tag $IMAGE_NAME ghcr.io/$NAMESPACE/$IMAGE_NAME

echo "Tagged $IMAGE_NAME as $IMAGE_NAME"


if [ "$1" == "no-push" ]; then
    echo "Skipping push to GHCR as 'no-push' argument is provided."
    exit 0
fi

docker push $IMAGE_NAME
echo "Pushed $IMAGE_NAME"