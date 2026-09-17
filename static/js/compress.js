async function compressImage(file, maxDimension = 1200, quality = 0.8) {
    return new Promise((resolve) => {
        if (!file) {
            resolve(file);
            return;
        }

        const isImage = (file.type && file.type.startsWith('image/')) || /\.(jpe?g|png|webp|gif|heic|heif)$/i.test(file.name);
        if (!isImage) {
            resolve(file);
            return;
        }
        
        let url;
        try {
            url = URL.createObjectURL(file);
        } catch (e) {
            resolve(file);
            return;
        }

        const img = new Image();
        
        img.onload = () => {
            URL.revokeObjectURL(url);
            
            try {
                let width = img.width;
                let height = img.height;
                
                if (width > maxDimension || height > maxDimension) {
                    if (width > height) {
                        height = Math.round(height * (maxDimension / width));
                        width = maxDimension;
                    } else {
                        width = Math.round(width * (maxDimension / height));
                        height = maxDimension;
                    }
                }
                
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                
                // Determine format support: if browser doesn't support WebP export, canvas.toDataURL returns image/png
                let targetType = 'image/webp';
                try {
                    const testUrl = canvas.toDataURL('image/webp', 0.5);
                    if (!testUrl.startsWith('data:image/webp')) {
                        targetType = 'image/jpeg';
                    }
                } catch (e) {
                    targetType = 'image/jpeg';
                }
                
                canvas.toBlob((blob) => {
                    if (blob) {
                        // Check if compression actually saved space, or if conversion was needed for HEIC/unsupported formats
                        const ext = targetType === 'image/webp' ? '.webp' : '.jpg';
                        const isOriginalWebSafe = /\.(jpe?g|png|webp|gif)$/i.test(file.name);
                        
                        if (isOriginalWebSafe && blob.size >= file.size) {
                            resolve(file); // Keep original if already compact
                            return;
                        }

                        let newName = file.name;
                        if (newName.includes('.')) {
                            newName = newName.substring(0, newName.lastIndexOf('.')) + ext;
                        } else {
                            newName += ext;
                        }

                        try {
                            const compressedFile = new File([blob], newName, { type: targetType, lastModified: Date.now() });
                            resolve(compressedFile);
                        } catch (e) {
                            // Fallback for environments where File constructor with blob fails
                            blob.name = newName;
                            blob.lastModifiedDate = new Date();
                            resolve(blob);
                        }
                    } else {
                        resolve(file);
                    }
                }, targetType, quality);
            } catch (err) {
                console.error("Compression error:", err);
                resolve(file);
            }
        };
        
        img.onerror = () => {
            URL.revokeObjectURL(url);
            resolve(file);
        };
        
        img.src = url;
    });
}

// Intercept form submission while compression is ongoing
document.addEventListener('submit', function(e) {
    const form = e.target;
    if (form && form.dataset && form.dataset.compressing === 'true') {
        e.preventDefault();
        e.stopImmediatePropagation();
        return false;
    }
}, true);

document.addEventListener('change', async function(e) {
    if (e.target && e.target.type === 'file' && e.target.accept && e.target.accept.includes('image/')) {
        const input = e.target;
        if (input.dataset.compressing === 'true') return;
        if (!input.files || input.files.length === 0) return;

        const file = input.files[0];
        const cacheKey = `${file.name}_${file.size}`;
        if (input.dataset.lastProcessed === cacheKey) return;

        const form = input.closest('form');
        let submitButtons = [];
        if (form) {
            form.dataset.compressing = 'true';
            submitButtons = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"]'));
            submitButtons.forEach(btn => {
                btn.disabled = true;
                btn.dataset.originalText = btn.innerHTML;
                if (btn.tagName === 'BUTTON') {
                    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> 压缩中...';
                }
            });
        }

        input.dataset.compressing = 'true';
        
        // Allow instant preview listener to execute first
        setTimeout(async () => {
            try {
                const compressed = await compressImage(file);
                if (compressed && compressed !== file && typeof DataTransfer !== 'undefined') {
                    const dt = new DataTransfer();
                    dt.items.add(compressed);
                    input.files = dt.files;
                    input.dataset.lastProcessed = `${compressed.name}_${compressed.size}`;
                    console.log(`[Image Compress] Original: ${(file.size / 1024).toFixed(1)}KB -> Compressed: ${(compressed.size / 1024).toFixed(1)}KB (${compressed.type})`);
                } else {
                    input.dataset.lastProcessed = cacheKey;
                }
            } catch (err) {
                console.error("[Image Compress] Failed to update file input:", err);
                input.dataset.lastProcessed = cacheKey;
            } finally {
                input.dataset.compressing = 'false';
                if (form) {
                    delete form.dataset.compressing;
                    submitButtons.forEach(btn => {
                        btn.disabled = false;
                        if (btn.tagName === 'BUTTON' && btn.dataset.originalText) {
                            btn.innerHTML = btn.dataset.originalText;
                        }
                    });
                }
            }
        }, 10);
    }
});
