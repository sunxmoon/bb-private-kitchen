/**
 * 宝宝的私房菜馆 — Interactive Cart & Batch Ordering System
 */
const Cart = (function() {
    const STORAGE_KEY = 'bb_kitchen_cart_v1';
    
    function loadCart() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
        } catch (e) {
            return {};
        }
    }

    function saveCart(cart) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(cart));
        } catch (e) {}
    }

    return {
        getItems() {
            return loadCart();
        },

        getTotalCount() {
            const cart = loadCart();
            let total = 0;
            for (const id in cart) {
                total += (cart[id].count || 0);
            }
            return total;
        },

        add(id, name, category, imageUrl) {
            const cart = loadCart();
            const sid = String(id);
            if (!cart[sid]) {
                cart[sid] = {
                    id: Number(id),
                    name: name || '菜品',
                    category: category || '',
                    imageUrl: imageUrl || '',
                    count: 1
                };
            } else {
                cart[sid].count = Math.min(cart[sid].count + 1, 20);
            }
            saveCart(cart);
            this.render();
            if (typeof showToast === 'function') {
                showToast(`已加入「${cart[sid].name}」`, 'info');
            }
        },

        sub(id) {
            const cart = loadCart();
            const sid = String(id);
            if (cart[sid]) {
                cart[sid].count -= 1;
                if (cart[sid].count <= 0) {
                    delete cart[sid];
                }
                saveCart(cart);
                this.render();
            }
        },

        clear() {
            saveCart({});
            this.render();
        },

        render() {
            const cart = loadCart();
            const totalCount = this.getTotalCount();

            // 1. Sync all stepper controls on the page
            document.querySelectorAll('[data-dish-stepper]').forEach(wrapper => {
                const dishId = wrapper.dataset.dishStepper;
                const count = (cart[dishId] && cart[dishId].count) || 0;
                const addBtn = wrapper.querySelector('.cart-add-btn');
                const stepper = wrapper.querySelector('.cart-stepper');
                const countEl = wrapper.querySelector('.cart-count-val');

                if (count > 0) {
                    if (addBtn) {
                        addBtn.classList.add('hidden');
                        addBtn.style.display = 'none';
                    }
                    if (stepper) {
                        stepper.classList.remove('hidden');
                        stepper.style.display = 'inline-flex';
                    }
                    if (countEl) countEl.textContent = count;
                } else {
                    if (addBtn) {
                        addBtn.classList.remove('hidden');
                        addBtn.style.display = 'inline-flex';
                    }
                    if (stepper) {
                        stepper.classList.add('hidden');
                        stepper.style.display = 'none';
                    }
                    if (countEl) countEl.textContent = '0';
                }
            });

            // 2. Sync Floating Cart Dock
            const dock = document.getElementById('floating-cart-dock');
            const dockBadge = document.getElementById('cart-dock-count-badge');
            const dockSummary = document.getElementById('cart-dock-summary');
            
            if (dock) {
                if (totalCount > 0) {
                    dock.classList.remove('hidden');
                    requestAnimationFrame(() => {
                        dock.classList.add('active');
                    });
                    if (dockBadge) dockBadge.textContent = totalCount;
                    if (dockSummary) {
                        const names = Object.values(cart).map(it => `${it.name}×${it.count}`);
                        dockSummary.textContent = names.slice(0, 3).join('、') + (names.length > 3 ? ' 等' : '');
                    }
                } else {
                    dock.classList.remove('active');
                    setTimeout(() => {
                        if (this.getTotalCount() === 0) {
                            dock.classList.add('hidden');
                        }
                    }, 200);
                }
            }

            // 3. If cart drawer modal is open, re-render drawer list
            this.renderDrawerList();
        },

        openDrawer() {
            this.renderDrawerList();
            if (typeof openModal === 'function') {
                openModal('cart-drawer-modal');
            }
        },

        renderDrawerList() {
            const listEl = document.getElementById('cart-drawer-items');
            if (!listEl) return;

            const cart = loadCart();
            const items = Object.values(cart);

            if (items.length === 0) {
                listEl.innerHTML = `
                    <div class="py-12 text-center text-stone-400">
                        <i class="fas fa-shopping-basket text-3xl mb-2 text-stone-300"></i>
                        <p class="text-sm font-bold">点餐篮空空如也</p>
                        <p class="text-xs text-stone-300 mt-1">快去菜单挑选心仪的美食吧</p>
                    </div>
                `;
                const submitBtn = document.getElementById('cart-submit-btn');
                if (submitBtn) submitBtn.disabled = true;
                return;
            }

            const submitBtn = document.getElementById('cart-submit-btn');
            if (submitBtn) submitBtn.disabled = false;

            listEl.innerHTML = items.map(item => `
                <div class="flex items-center justify-between p-3 rounded-2xl bg-stone-50 border border-stone-100">
                    <div class="flex items-center gap-3 min-w-0 flex-1">
                        ${item.imageUrl ? `
                            <img src="${item.imageUrl}" class="w-12 h-12 rounded-xl object-cover shrink-0 border border-stone-200">
                        ` : `
                            <div class="w-12 h-12 rounded-xl bg-orange-100/50 text-orange-500 flex items-center justify-center shrink-0">
                                <i class="fas fa-utensils text-sm"></i>
                            </div>
                        `}
                        <div class="min-w-0 flex-1">
                            <h4 class="font-bold text-sm text-stone-800 truncate">${item.name}</h4>
                            ${item.category ? `<span class="text-[10px] text-stone-400 font-medium">${item.category}</span>` : ''}
                        </div>
                    </div>
                    <div class="stepper shrink-0 ml-3">
                        <button type="button" class="stepper-btn" onclick="Cart.sub(${item.id})">
                            <i class="fas fa-minus text-[10px]"></i>
                        </button>
                        <span class="stepper-value text-xs font-bold px-1">${item.count}</span>
                        <button type="button" class="stepper-btn" onclick="Cart.add(${item.id}, '${item.name}', '${item.category}', '${item.imageUrl}')">
                            <i class="fas fa-plus text-[10px]"></i>
                        </button>
                    </div>
                </div>
            `).join('');
        },

        async submitOrder() {
            const cart = loadCart();
            const items = Object.values(cart);
            if (items.length === 0) return;

            const submitBtn = document.getElementById('cart-submit-btn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1.5"></i> 正在下单...';
            }

            // Gather preference chips
            const tasteChip = document.querySelector('.taste-chip.active');
            const timeChip = document.querySelector('.time-chip.active');
            const remarksInput = document.getElementById('cart-remarks-input');

            const payload = {
                items: items.map(it => ({
                    dish_id: it.id,
                    quantity: it.count,
                    taste: tasteChip ? tasteChip.dataset.val : null,
                    preferred_time: timeChip ? timeChip.dataset.val : null,
                    remarks: remarksInput ? remarksInput.value.trim() : null
                })),
                global_taste: tasteChip ? tasteChip.dataset.val : null,
                global_time: timeChip ? timeChip.dataset.val : null,
                global_remarks: remarksInput ? remarksInput.value.trim() : null
            };

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

            try {
                const response = await fetch('/api/orders/batch', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    Cart.clear();
                    if (typeof closeModal === 'function') {
                        closeModal('cart-drawer-modal');
                    }
                    if (typeof showToast === 'function') {
                        showToast('点餐成功！大厨马上开始制作~', 'success');
                    }
                    setTimeout(() => {
                        window.location.href = '/my-orders';
                    }, 400);
                } else {
                    const err = await response.json();
                    alert(err.detail || '下单失败，请重试');
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = '确认下单';
                    }
                }
            } catch (err) {
                console.error('Batch order failed:', err);
                alert('网络连接错误，请检查网络');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '确认下单';
                }
            }
        }
    };
})();

// Preference chip toggles
document.addEventListener('click', function(e) {
    const chip = e.target.closest('.pref-chip');
    if (chip) {
        const parent = chip.parentElement;
        parent.querySelectorAll('.pref-chip').forEach(c => c.classList.remove('active', 'bg-orange-500', 'text-white'));
        parent.querySelectorAll('.pref-chip').forEach(c => c.classList.add('bg-stone-100', 'text-stone-600'));
        chip.classList.remove('bg-stone-100', 'text-stone-600');
        chip.classList.add('active', 'bg-orange-500', 'text-white');
    }
});

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    Cart.render();
});
