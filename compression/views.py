import os, io, zlib, pickle, base64
import numpy as np
import pywt
import torch
import torch.nn as nn
import torch.optim as optim
from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from PIL import Image
from skimage import io as skio, img_as_float
from .forms import ImageUploadForm

# ----------------------------
# Wavelet Transform Utilities
# ----------------------------
def wavelet_transform(image, wavelet='haar'):
    coeffs = pywt.dwt2(image, wavelet)
    return coeffs

def pack_coeffs(coeffs):
    LL, (LH, HL, HH) = coeffs
    top = np.concatenate([LL, LH], axis=1)
    bottom = np.concatenate([HL, HH], axis=1)
    packed = np.concatenate([top, bottom], axis=0)
    return packed

def unpack_coeffs(packed):
    h, w = packed.shape
    h2, w2 = h // 2, w // 2
    LL = packed[:h2, :w2]
    LH = packed[:h2, w2:]
    HL = packed[h2:, :w2]
    HH = packed[h2:, w2:]
    return (LL, (LH, HL, HH))

def inverse_wavelet_transform_packed(packed, wavelet='haar'):
    coeffs = unpack_coeffs(packed)
    reconstructed = pywt.idwt2(coeffs, wavelet)
    return reconstructed

# ----------------------------
# SIREN (Implicit Neural Representation)
# ----------------------------
class SineLayer(nn.Module):
    def __init__(self, in_features, out_features, is_first=False, omega_0=30):
        super().__init__()
        self.omega_0 = omega_0
        self.is_first = is_first
        self.linear = nn.Linear(in_features, out_features)
        self.init_weights()
        
    def init_weights(self):
        with torch.no_grad():
            if self.is_first:
                self.linear.weight.uniform_(-1 / self.linear.in_features, 1 / self.linear.in_features)
            else:
                bound = np.sqrt(6 / self.linear.in_features) / self.omega_0
                self.linear.weight.uniform_(-bound, bound)
                
    def forward(self, input):
        return torch.sin(self.omega_0 * self.linear(input))

class SIREN(nn.Module):
    def __init__(self, in_features, hidden_features, hidden_layers, out_features, omega_0=30):
        super().__init__()
        layers = [SineLayer(in_features, hidden_features, is_first=True, omega_0=omega_0)]
        for _ in range(hidden_layers):
            layers.append(SineLayer(hidden_features, hidden_features, is_first=False, omega_0=omega_0))
        self.net = nn.Sequential(*layers)
        self.final_linear = nn.Linear(hidden_features, out_features)
        
    def forward(self, coords):
        x = self.net(coords)
        out = self.final_linear(x)
        return out

def train_inr(coords, targets, model, num_epochs=100, lr=1e-3):
    model.train()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    coords_tensor = torch.tensor(coords, dtype=torch.float32)
    targets_tensor = torch.tensor(targets, dtype=torch.float32)
    
    for epoch in range(num_epochs):
        optimizer.zero_grad()
        outputs = model(coords_tensor)
        loss = loss_fn(outputs, targets_tensor)
        loss.backward()
        optimizer.step()
    return model

def compress_residuals(residuals):
    # Quantize to 8-bit to significantly reduce size
    min_val = residuals.min()
    max_val = residuals.max()
    
    # Avoid division by zero
    if max_val == min_val:
        scale = 1.0
        q_residuals = np.zeros_like(residuals, dtype=np.uint8)
    else:
        scale = 255.0 / (max_val - min_val)
        q_residuals = np.round((residuals - min_val) * scale).astype(np.uint8)
    
    # Store metadata needed for reconstruction
    # We must store min/max as float32 to preserve range info
    metadata = {'min': min_val.astype(np.float32), 'max': max_val.astype(np.float32), 'shape': residuals.shape}
    
    # Serialize the quantized data and metadata
    data_bytes = pickle.dumps((metadata, q_residuals))
    compressed = zlib.compress(data_bytes, level=9)
    return compressed

def decompress_residuals(compressed):
    data_bytes = zlib.decompress(compressed)
    metadata, q_residuals = pickle.loads(data_bytes)
    
    min_val = metadata['min']
    max_val = metadata['max']
    
    # Dequantize
    if max_val == min_val:
        residuals = np.full(metadata['shape'], min_val, dtype=np.float32)
    else:
        scale = 255.0 / (max_val - min_val)
        # Convert back to float32
        residuals = (q_residuals.astype(np.float32) / scale) + min_val
        
    return residuals

from pydicom import dcmread

def process_image(image_path):
    # Check if the file is a DICOM file based on extension
    if image_path.lower().endswith('.dcm'):
        ds = dcmread(image_path)
        # Get the pixel data from the DICOM file
        image = ds.pixel_array.astype(np.float32)
        # Normalize the image to the range [0, 1]
        image = image / np.max(image)
    else:
        # Load non-DICOM image (e.g., PNG, JPG)
        # Removed as_gray=True to support color images
        image = img_as_float(skio.imread(image_path))
    
def _process_array(image):
    """
    Helper function to process a numpy image array (RGB or Grayscale).
    Returns (reconstructed_image, compressed_residuals, max_error)
    """
    # Ensure image has channels dimension if it's grayscale
    if image.ndim == 2:
        image = image[..., np.newaxis]
    
    # Downsample the image for faster processing
    # Slice first two dimensions (H, W), keep channels
    # Note: If image is already downsampled or small, this might reduce quality further
    image_down = image[::2, ::2, :]
    
    H_img, W_img, C = image_down.shape
    
    # Apply wavelet transform and pack coefficients per channel
    packed_channels = []
    for c in range(C):
        coeffs = wavelet_transform(image_down[..., c], wavelet='haar')
        packed = pack_coeffs(coeffs)
        packed_channels.append(packed)
    
    # Stack channels back together: (H_packed, W_packed, C)
    packed_coeffs = np.stack(packed_channels, axis=-1)
    H, W, _ = packed_coeffs.shape
    
    # Prepare coordinate and target arrays
    ys, xs = np.meshgrid(np.linspace(0, 1, H), np.linspace(0, 1, W), indexing='ij')
    coords = np.stack([xs.flatten(), ys.flatten()], axis=-1)
    
    # Targets: flatten spatial dims but keep channels: (N_pixels, C)
    targets = packed_coeffs.reshape(-1, C)
    
    # Train the SIREN model
    model = SIREN(in_features=2, hidden_features=32, hidden_layers=2, out_features=C, omega_0=30)
    model = train_inr(coords, targets, model, num_epochs=100, lr=1e-3)
    
    # Predict coefficients
    model.eval()
    with torch.no_grad():
        coords_tensor = torch.tensor(coords, dtype=torch.float32)
        predictions = model(coords_tensor).numpy()
        
    predicted_coeffs = predictions.reshape(H, W, C)
    
    # Compute residuals and compress them
    residuals = packed_coeffs - predicted_coeffs
    compressed_residuals = compress_residuals(residuals)
    
    # Decompress residuals
    decompressed_residuals = decompress_residuals(compressed_residuals)
    
    # Reconstruct packed coefficients
    reconstructed_packed = predicted_coeffs + decompressed_residuals
    
    # Inverse wavelet transform per channel
    reconstructed_channels = []
    for c in range(C):
        rec_packed_c = reconstructed_packed[..., c]
        rec_img_c = inverse_wavelet_transform_packed(rec_packed_c, wavelet='haar')
        reconstructed_channels.append(rec_img_c)
        
    reconstructed_image = np.stack(reconstructed_channels, axis=-1)
    
    # Crop to original downsampled dimensions if needed
    reconstructed_image = reconstructed_image[:H_img, :W_img, :]

    error = np.abs(image_down - reconstructed_image)
    max_error = np.max(error)
    
    # Squeeze if single channel
    if C == 1:
        reconstructed_image = reconstructed_image.squeeze(axis=-1)
    
    return reconstructed_image, compressed_residuals, max_error

def process_image(image_path):
    # Check if the file is a DICOM file based on extension
    if image_path.lower().endswith('.dcm'):
        ds = dcmread(image_path)
        image = ds.pixel_array.astype(np.float32)
        image = image / np.max(image)
    else:
        # Load non-DICOM image (RGB)
        image_rgb = img_as_float(skio.imread(image_path))
        # Create Grayscale version
        image_bw = img_as_float(skio.imread(image_path, as_gray=True))

    # Process RGB
    print("Processing RGB...")
    if image_rgb.ndim == 2: # handle case if uploaded image was already gray
         image_rgb = image_rgb[..., np.newaxis]
    recon_rgb, comp_rgb, error_rgb = _process_array(image_rgb)
    
    # Process BW
    print("Processing BW...")
    recon_bw, comp_bw, error_bw = _process_array(image_bw)
    
    # Return both sets of results
    # image_rgb is expected to be returned downsampled in the original code flow for consistency with display 
    # but since we moved downsampling inside _process_array, we should probably just return the original or downsampled version 
    # for display. The 'orig' returned previously was the *input* to process_image but downsampled. 
    # Let's align with that: return the downsampled input so it matches the reconstruction size.
    
    orig_rgb_down = image_rgb[::2, ::2, :]
    if orig_rgb_down.shape[2] == 1: orig_rgb_down = orig_rgb_down.squeeze(axis=-1)
        
    return orig_rgb_down, recon_rgb, comp_rgb, error_rgb, recon_bw, comp_bw, error_bw


# ----------------------------
# Django Views
# ----------------------------
from django.http import HttpResponse
from django.shortcuts import render
from .forms import ImageUploadForm

def compress_view(request):
    context = {}
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['image']
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            temp_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.name)
            with open(temp_path, 'wb+') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            # Process the image
            orig, recon, comp_data, max_error, recon_bw, comp_data_bw, max_error_bw = process_image(temp_path)
            
            # Calculate sizes in MB
            orig_size_bytes = os.path.getsize(temp_path)
            comp_size_bytes = len(comp_data)
            comp_size_bw_bytes = len(comp_data_bw)
            orig_size_mb = orig_size_bytes / (1024 * 1024)
            comp_size_mb = comp_size_bytes / (1024 * 1024)
            comp_size_bw_mb = comp_size_bw_bytes / (1024 * 1024)
            
            # Update context with sizes in MB
            context['orig_size'] = f"{orig_size_mb:.2f} MB"
            context['comp_size'] = f"{comp_size_mb:.2f} MB"
            context['max_error'] = max_error
            context['comp_size_bw'] = f"{comp_size_bw_mb:.2f} MB"
            context['max_error_bw'] = max_error_bw
            
            # Convert numpy arrays to base64 for display (using a helper function, e.g., to_base64)
            def to_base64(img_array):
                img = Image.fromarray((np.clip(img_array, 0, 1) * 255).astype(np.uint8))
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            context['orig_img'] = to_base64(orig)
            recon_b64 = to_base64(recon)
            recon_bw_b64 = to_base64(recon_bw)
            
            context['recon_img'] = recon_b64
            context['recon_img_bw'] = recon_bw_b64
            
            # Save compressed data and images in session for download option
            request.session['comp_data'] = base64.b64encode(comp_data).decode('utf-8')
            request.session['recon_img'] = recon_b64
            request.session['recon_img_bw'] = recon_bw_b64
            
            os.remove(temp_path)
    else:
        form = ImageUploadForm()
    context['form'] = form
    return render(request, 'compression/process_image.html', context)


def download_compressed(request):
    comp_data_b64 = request.session.get('comp_data', None)
    if comp_data_b64:
        comp_data = base64.b64decode(comp_data_b64)
        response = HttpResponse(comp_data, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="compressed.bin"'
        return response
    return HttpResponse("No compressed data available.")

def download_recon_rgb(request):
    img_b64 = request.session.get('recon_img', None)
    if img_b64:
        img_data = base64.b64decode(img_b64)
        response = HttpResponse(img_data, content_type='image/png')
        response['Content-Disposition'] = 'attachment; filename="reconstructed_rgb.png"'
        return response
    return HttpResponse("No image available.")

def download_recon_bw(request):
    img_b64 = request.session.get('recon_img_bw', None)
    if img_b64:
        img_data = base64.b64decode(img_b64)
        response = HttpResponse(img_data, content_type='image/png')
        response['Content-Disposition'] = 'attachment; filename="reconstructed_bw.png"'
        return response
    return HttpResponse("No image available.")
