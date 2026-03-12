# Medical Image Compression Project

A Django-based web application that uses a custom "Wavelet Transform + SIREN (Implicit Neural Representation)" algorithm to compress medical and standard images. The system now supports both **RGB Color** and **Grayscale** processing in parallel.

## Features
-   **Dual Output Processing**: Automatically processes uploaded images in both Color (RGB) and Black & White (Grayscale).
-   **Advanced Compression**: Uses Wavelet decomposition followed by a Neural Network (SIREN) to model image coefficients, achieving high compression ratios.
-   **Quantization**: Implements 8-bit quantization for efficient storage.
-   **Downloadable Results**: Users can download the reconstructed images (PNG) and the raw compressed binary data.

## Prerequisites
-   Python 3.8 or higher.
-   Pip (Python package manager).

## Installation

1.  **Extract the Project**:
    -   Unzip the folder to your desired location (e.g., `D:\myproject`).
    -   Open a terminal/command prompt in this folder.

2.  **Create a Virtual Environment** (Recommended):
    -   It is best to run this project in an isolated environment.
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment**:
    -   **Windows**:
        ```bash
        .\venv\Scripts\activate
        ```
    -   **Mac/Linux**:
        ```bash
        source venv/bin/activate
        ```

4.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: If you don't have `requirements.txt`, install manually: `pip install django numpy torch PyWavelets scikit-image pydicom Pillow`)*

5.  **Apply Migrations**:
    ```bash
    python manage.py migrate
    ```

## Running the Application

1.  **Start the Server**:
    ```bash
    python manage.py runserver
    ```

2.  **Access the App**:
    Open your web browser and go to:
    [http://127.0.0.1:8000/compression/](http://127.0.0.1:8000/compression/)

## Usage Guide

1.  **Upload**: Click "Choose File" and select an image (JPG, PNG, or DICOM).
2.  **Process**: Click "Process Image". Use the console to see progress (training the neural network takes a few seconds).
3.  **View Results**:
    -   See the **Color** result and **Black & White** result side-by-side.
    -   Compare "Original Size" vs "Compressed Size".
    -   Check "Max Reconstruction Error" to see quality metrics.
4.  **Download**:
    -   Click **Download Image** under each version to save the reconstructed PNG.
    -   Click **Download Compressed Data** to get the raw binary file.
