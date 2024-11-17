# The Most Polish Landscape (Visualizer)

This Python application renders and animates a slideshow of AI-generated landscape images with smooth interpolation and an optional overlay. It’s designed for fullscreen display at a high resolution, ideal for art installations or exhibitions.

---

## Installation

Clone this repository and install the required dependencies:

```bash
git clone https://github.com/speplinski/tmpl-visualizer.git
cd tmpl-visualizer/
pip install -r requirements.txt
```

## Dataset Preparation

This application can use pre-generated test images for demonstration purposes. To prepare the dataset:


```bash
cd results/
./download_images.sh
cd ..
```

This script will download and extract the required dataset files and organize them into the appropriate structure under the `results/` directory.

For the final system, the application should point to the directory where images are generated in real-time by the GPU and saved by the AI model.

## Usage

Run the script using Python:

```bash
python app.py
```

## Key Features

- **Smooth Interpolation**: Transition seamlessly between consecutive images using advanced interpolation techniques.
- **Overlay Support**: Apply a transparent overlay on the images for additional visual effects.
- **Real-Time Adaptability**: Designed to read images directly from the GPU’s output directory in a production environment.
