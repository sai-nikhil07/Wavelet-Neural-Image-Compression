# Project Description: Medical Image Compression using Dual-Channel Processing with Wavelet Transform and SIREN

## 1. Project Overview
This project is an advanced image compression system designed specifically for medical imaging (DICOM files, MRIs, X-Rays) while also supporting standard high-resolution color imagery (PNG, JPG). The core objective is to significantly reduce the storage footprint of digital images without compromising diagnostic or visual quality. 

The system employs a cutting-edge hybrid approach, combining traditional mathematical decomposition (**Discrete Wavelet Transform**) with modern Deep Learning techniques **(SIREN - Sinusoidal Representation Networks)**.

## 2. Problem Statement
Medical facilities generate petabytes of high-resolution digital imaging data annually. Storing and transmitting these massive raw files (like DICOM) is expensive and bandwidth-intensive. Traditional lossy compression algorithms (like JPEG) often introduce "artifacts" (blockiness or blurring) that can obscure critical medical details. There is a need for a compression algorithm that can achieve high compression ratios while retaining high-frequency structural details essential for medical diagnosis.

## 3. The Solution & Architecture
Our solution attacks the compression problem in two phases: frequency separation and neural memorization.

### Phase A: Frequency Separation (Wavelet Transform)
Instead of processing the raw pixels, the image first passes through a **2D Discrete Wavelet Transform (Haar Wavelet)**. 
- This mathematical operation splits the image into four sub-bands: Low-Low (overall shape), Low-High (horizontal edges), High-Low (vertical edges), and High-High (diagonal details).
- **Why this matters:** Medical images consist mostly of smooth areas (Low frequencies) with sudden, sharp details like bone edges or tumors (High frequencies). Separating them makes the data easier to compress.

### Phase B: Neural Memorization (SIREN)
The packed Wavelet coefficients are then fed into a **SIREN (Sinusoidal Representation Network)**.
- Unlike Convolutional Neural Networks (CNNs) that look for features, SIREN is an *Implicit Neural Representation*. 
- It essentially "memorizes" the image. The network takes pixel coordinates (X, Y) as input and outputs the exact Wavelet coefficients at that location.
- **Why this matters:** Instead of saving millions of pixels, we only need to save the tiny "weights" of this small neural network. The neural network *becomes* the image.

### Phase C: Residual Quantization
No neural network is perfectly accurate. To guarantee high quality, the system calculates the "Residuals" (the difference between the original Wavelet data and the Neural Network's prediction).
- These residuals are mapped from 32-bit high-precision floats down to **8-bit integers (Quantization)**.
- Finally, they are passed through traditional `zlib` lossless compression.

### Phase D: Reconstruction
To view the image, the receiver executes the Neural Network to generate the base image, adds the Decompressed Residuals to fix the fine details, and finally applies the Inverse Wavelet Transform.

---

## 4. Key Features & Innovations implemented
1. **Dual-Channel Processing Pipeline:** 
   Fully supports uploading a standard color image (RGB). The system automatically processes the image twice in parallel: once preserving full color channels, and once strictly as Grayscale. Both results and their compression metrics are displayed side-by-side for analysis.
2. **Format Agnostic:** 
   Natively processes standard web formats (JPG, PNG) alongside specialized clinical formats (`.dcm` DICOM pixel arrays) using `pydicom`.
3. **Automated Downsampling:** 
   Automatically scales images intelligently to ensure the memory footprint during server-side Neural Network training remains stable, making it viable for web-app deployment.
4. **Interactive Web Interface:** 
   Built entirely on Django. End-users interact with a clean UI, review Original vs. Reconstructed images visually, and can directly download both the Reconstructed PNGs and the raw binary compressed payload.
5. **Real-time Metric Calculation:** 
   Dynamically calculates and displays the exact byte-size savings and the "Max Reconstruction Error" (Absolute Maximum Pixel Difference), proving the fidelity of the compression.

## 5. Technology Stack
*   **Backend Framework:** Django (Python)
*   **Neural Network Engine:** PyTorch (`torch`, `torch.nn`)
*   **Mathematical Processing:** NumPy, PyWavelets (`pywt`)
*   **Image Handling:** Pillow (`PIL`), `scikit-image`, `pydicom`
*   **Data Serialization:** `pickle`, `zlib`, Base64 encoding
*   **Frontend:** HTML5, CSS3, Django Template Language
