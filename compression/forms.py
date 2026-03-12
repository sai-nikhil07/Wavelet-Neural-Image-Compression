from django import forms

class ImageUploadForm(forms.Form):
    image = forms.FileField(label="Select a medical image (.png, .jpg, .jpeg, .bmp, .dcm)")
