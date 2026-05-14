document.addEventListener('DOMContentLoaded', () => {
    const navItems = document.querySelectorAll('.nav-item');
    const navIndicator = document.querySelector('.nav-indicator');
    const views = document.querySelectorAll('.view');
    const pageTitle = document.getElementById('page-title');
    const pillNavItems = document.querySelectorAll('.nav-pill .nav-item');

    function isDesktop() {
        return window.innerWidth >= 768;
    }

    // Telegram WebApp Object
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.expand();
        tg.ready();
    }

    /*
    // --- Security: URL Cleanup ---
    function cleanupUrl() {
        console.log('cleanupUrl: checking params...');
        const url = new URL(window.location.href);
        if (url.searchParams.has('tg_id') || url.searchParams.has('tg_username')) {
            url.searchParams.delete('tg_id');
            url.searchParams.delete('tg_username');
            console.log('cleanupUrl: applying replaceState to', url.toString());
            try {
                window.history.replaceState({}, document.title, url.toString());
                console.log('cleanupUrl: success');
            } catch (e) {
                console.error('cleanupUrl: error', e);
            }
        }
    }
    cleanupUrl();
    */

    // Initialize indicator position
    function updateIndicator(activeItem) {
        if (!activeItem || !navIndicator) return;

        if (activeItem.closest('.nav-pill')) {
            const offsetL = activeItem.offsetLeft;
            const offsetT = activeItem.offsetTop;
            const width = activeItem.offsetWidth;
            const height = activeItem.offsetHeight;

            if (isDesktop()) {
                // Vertical Rail mode
                navIndicator.style.transform = `translateY(${offsetT}px)`;
                navIndicator.style.height = `${height}px`;
                navIndicator.style.width = 'auto'; // Width handled by CSS left/right
            } else {
                // Horizontal Pill mode
                navIndicator.style.transform = `translateX(${offsetL}px)`;
                navIndicator.style.width = `${width}px`;
                navIndicator.style.height = 'auto'; // Height handled by CSS top/bottom
            }
            navIndicator.style.opacity = '1';
        } else {
            // Profile clicked
            navIndicator.style.opacity = '0.5';
        }
    }

    // Update on resize
    window.addEventListener('resize', () => {
        const activeItem = document.querySelector('.nav-item.active');
        // Reset inline styles that might conflict
        navIndicator.style.width = '';
        navIndicator.style.height = '';
        navIndicator.style.transform = '';
        updateIndicator(activeItem);
    });

    // Set initial state
    document.fonts.ready.then(() => {
        document.body.classList.add('fonts-loaded');
        const initialActive = document.querySelector('.nav-item.active');
        updateIndicator(initialActive);
    });

    // Navigation Click Handler
    function activateTab(item) {
        const targetId = item.getAttribute('data-target');
        const targetTitle = item.getAttribute('data-title');

        // Haptic Feedback for navigation
        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        }

        navItems.forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');
        updateIndicator(item);

        if (pageTitle && targetTitle) {
            pageTitle.style.opacity = '0';
            pageTitle.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                pageTitle.textContent = targetTitle;
                pageTitle.style.opacity = '1';
                pageTitle.style.transform = 'translateY(0)';
            }, 150);
        }

        // Slide animation logic (only for mobile)
        const viewArray = Array.from(views);
        const index = viewArray.findIndex(v => v.id === targetId);
        const wrapper = document.getElementById('view-wrapper');

        if (index !== -1 && wrapper && !isDesktop()) {
            const offset = index * (100 / views.length);
            wrapper.style.transform = `translateX(-${offset}%)`;
        } else if (wrapper) {
            wrapper.style.transform = ''; // Clear transform on desktop
        }

        views.forEach(view => {
            if (view.id === targetId) {
                view.classList.add('active');
            } else {
                view.classList.remove('active');
            }
        });

        const profileNav = document.querySelector('.nav-profile');
        if (profileNav) {
            if (targetId === 'view-profile') {
                profileNav.classList.add('active-bg');
            } else {
                profileNav.classList.remove('active-bg');
            }
        }

        sessionStorage.setItem('activeTab', targetId);
        sessionStorage.setItem('activeTitle', targetTitle);
    }

    navItems.forEach(item => {
        item.addEventListener('click', () => activateTab(item));
    });

    window.activateTabById = (viewId, title) => {
        const item = Array.from(navItems).find(i => i.getAttribute('data-target') === viewId);
        if (item) {
            activateTab(item);
        } else {
            // Haptic Feedback
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
                window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
            }

            navItems.forEach(nav => nav.classList.remove('active'));
            if (pageTitle) pageTitle.textContent = title;

            // Slide animation for sub-views (only for mobile)
            const viewArray = Array.from(views);
            const index = viewArray.findIndex(v => v.id === viewId);
            const wrapper = document.getElementById('view-wrapper');

            if (index !== -1 && wrapper && !isDesktop()) {
                const offset = index * (100 / views.length);
                wrapper.style.transform = `translateX(-${offset}%)`;
            } else if (wrapper) {
                wrapper.style.transform = '';
            }

            views.forEach(v => {
                if (v.id === viewId) v.classList.add('active');
                else v.classList.remove('active');
            });
        }
    };

    // Global haptic feedback for all buttons and interactive elements
    document.addEventListener('click', (e) => {
        const target = e.target.closest('.bounce, .action-btn, .v2-buy-btn, .nav-item, .settings-item');
        if (target && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        }
    });

    // Restore active tab after page reload
    const savedTab = sessionStorage.getItem('activeTab');
    if (savedTab) {
        const savedItem = Array.from(navItems).find(
            item => item.getAttribute('data-target') === savedTab
        );
        if (savedItem) {
            activateTab(savedItem);
        }
    }


    // Drag-to-scroll for card-list on PC
    const slider = document.querySelector('.card-list-vertical'); // Switched to vertical so maybe not needed, but keep for fallback
    if (slider) {
        let isDown = false;
        let startY;
        let scrollTop;

        slider.addEventListener('mousedown', (e) => {
            isDown = true;
            slider.style.cursor = 'grabbing';
            startY = e.pageY - slider.offsetTop;
            scrollTop = slider.scrollTop;
        });

        slider.addEventListener('mouseleave', () => {
            if (!isDown) return;
            isDown = false;
            slider.style.cursor = '';
        });

        slider.addEventListener('mouseup', () => {
            isDown = false;
            slider.style.cursor = '';
        });

        slider.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            e.preventDefault();
            const y = e.pageY - slider.offsetTop;
            const walk = (y - startY) * 2;
            slider.scrollTop = scrollTop - walk;
        });
    }

    function initTelegram() {
        let user = null;

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe?.user) {
            const tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();
            user = tg.initDataUnsafe.user;
        } else if (IS_DEBUG && MOCK_USER_DATA) {
            console.log('Using mock user data for development');
            user = MOCK_USER_DATA;
        }

        if (user) {
            // Check if URL has the correct ID
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('tg_id') != user.id) {
                urlParams.set('tg_id', user.id);
                if (user.username) {
                    urlParams.set('tg_username', user.username);
                }
                window.location.search = urlParams.toString();
                return;
            }

            const profileName = document.getElementById('profile-name');
            const profileUserid = document.getElementById('profile-userid');
            const connectionUsername = document.getElementById('connection-username');
            const profileAvatar = document.getElementById('profile-avatar');

            const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ');
            if (profileName) {
                profileName.textContent = fullName || user.username || 'Пользователь Telegram';
            }

            if (profileUserid) {
                profileUserid.textContent = `ID: ${user.id}`;
            }

            if (connectionUsername) {
                const displayName = user.username ? `@${user.username}` : user.first_name;
                connectionUsername.textContent = displayName;
            }

            if (profileAvatar) {
                if (user.photo_url) {
                    profileAvatar.innerHTML = `<img src="${user.photo_url}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover; border: 2px solid var(--md-sys-color-primary-container);">`;
                } else {
                    const initial = (user.first_name || user.username || 'U').charAt(0).toUpperCase();
                    profileAvatar.innerHTML = `<span style="font-size: 28px; font-weight: 500;">${initial}</span>`;
                }
            }
        }
    }

    initTelegram();

    // Modal Handling
    const modalOverlay = document.getElementById('modal-overlay');
    const modalTitle = document.getElementById('modal-title');
    const modalMessage = document.getElementById('modal-message');
    const modalIcon = document.getElementById('modal-icon-text');
    const modalClose = document.getElementById('modal-close');
    const modalAction = document.getElementById('modal-action');
    const modalInputContainer = document.getElementById('modal-input-container');
    const modalAmountInput = document.getElementById('modal-amount-input');

    let lastModalTime = 0;

    function showModal({ title, message, icon = 'info', actionText = 'Пополнить', onAction = null, showInput = false, inputValue = '', inputPlaceholder = 'Введите данные...', inputType = 'text', customHtml = '', closeBtnText = 'Закрыть' }) {
        lastModalTime = Date.now();
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        modalIcon.textContent = icon;
        modalAction.textContent = actionText;
        modalClose.textContent = closeBtnText;

        if (showInput) {
            modalInputContainer.style.display = 'block';
            modalAmountInput.value = inputValue;
            modalAmountInput.placeholder = inputPlaceholder;
            modalAmountInput.type = inputType;
            modalAmountInput.focus();
        } else {
            modalInputContainer.style.display = 'none';
        }

        let customContainer = document.getElementById('modal-custom-content');
        if (!customContainer) {
            customContainer = document.createElement('div');
            customContainer.id = 'modal-custom-content';
            customContainer.style.width = '100%';
            customContainer.style.marginTop = '15px';
            modalInputContainer.parentNode.insertBefore(customContainer, modalInputContainer);
        }

        if (customHtml) {
            customContainer.style.display = 'block';
            customContainer.innerHTML = customHtml;
        } else {
            customContainer.style.display = 'none';
            customContainer.innerHTML = '';
        }

        if (onAction) {
            modalAction.style.display = 'block';
            modalAction.onclick = () => {
                const currentModalTime = lastModalTime = Date.now();
                onAction();
                // Only hide if no other modal was opened during onAction
                if (lastModalTime === currentModalTime) {
                    hideModal();
                }
            };
        } else {
            modalAction.style.display = 'none';
        }

        modalOverlay.classList.add('active');
    }

    function hideModal() {
        modalOverlay.classList.remove('active');
        modalClose.textContent = 'Закрыть';
        // Clean up extra buttons if any
        document.querySelectorAll('.test-topup-extra').forEach(el => el.remove());
    }

    modalClose.onclick = hideModal;
    modalOverlay.onclick = (e) => {
        if (e.target === modalOverlay) hideModal();
    };

    window.handleTopup = (initialAmount = '') => {
        const message = initialAmount 
            ? `На вашем счёте недостаточно ${initialAmount} ₽. Введите сумму для пополнения:`
            : 'Введите сумму, на которую вы хотите пополнить счёт:';

        showModal({
            title: 'Пополнение баланса',
            message: message,
            icon: 'payments',
            actionText: 'Пополнить',
            showInput: true,
            inputValue: initialAmount,
            inputPlaceholder: 'Сумма в рублях',
            inputType: 'number',
            onAction: () => {
                const amount = parseFloat(modalAmountInput.value);
                if (isNaN(amount) || amount <= 0) {
                    alert('Пожалуйста, введите корректную сумму.');
                    return;
                }
                performTopup(amount);
            }
        });
    };

    async function performTopup(amount) {
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

        if (!userId || userId === 'undefined') {
            showModal({
                title: 'Ошибка',
                message: 'Ваш профиль еще не загружен. Пожалуйста, подождите секунду и попробуйте снова.',
                icon: 'hourglass_empty',
                actionText: 'Ок',
                onAction: hideModal
            });
            return;
        }

        try {
            const formData = new FormData();
            formData.append('amount', amount);
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

            if (tg?.initData) {
                formData.append('init_data', tg.initData);
            } else {
                formData.append('tg_id', userId);
            }

            const response = await fetch('/shop/topup-api/', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                const balanceAmount = document.getElementById('profile-balance');
                if (balanceAmount) {
                    balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
                }

                // Remove extra buttons
                document.querySelectorAll('.test-topup-extra').forEach(el => el.remove());

                showModal({
                    title: 'Готово!',
                    message: `Ваш баланс успешно пополнен на ${amount} ₽.`,
                    icon: 'check_circle',
                    actionText: 'Отлично',
                    onAction: () => {
                        hideModal();
                        if (window.syncNow) window.syncNow();
                    }
                });
                // Also trigger sync immediately in background
                if (window.syncNow) window.syncNow();
            } else {
                showModal({
                    title: 'Ошибка',
                    message: data.error || 'Не удалось пополнить баланс.',
                    icon: 'error',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            }
        } catch (error) {
            showModal({
                title: 'Ошибка сети',
                message: 'Проверьте интернет-соединение.',
                icon: 'cloud_off',
                actionText: 'Ок',
                onAction: hideModal
            });
        }
    }

    // Loading Animation
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    const spinner = loadingOverlay?.querySelector('.spinner');
    const successIcon = loadingOverlay?.querySelector('.success-icon-wrapper');

    function showLoading(text = 'Обработка...') {
        loadingText.textContent = text;
        loadingOverlay.classList.remove('success');
        loadingOverlay.classList.add('active');
    }

    function showSuccessAnim(callback) {
        loadingOverlay.classList.add('success');
        if (successIcon) successIcon.style.display = 'flex';
        if (spinner) spinner.style.display = 'none';
        
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
        }
        setTimeout(() => {
            if (successIcon) successIcon.style.display = 'none';
            if (spinner) spinner.style.display = 'block';
            loadingOverlay.classList.remove('active');
            if (callback) callback();
        }, 500); // Wait for animation to complete
    }

    function hideLoading() {
        loadingOverlay.classList.remove('active');
        loadingOverlay.classList.remove('success');
    }

    async function performBuy(tariffId, price, userId, username, replace = false) {
        showLoading(replace ? 'Замена подписки...' : 'Оформление подписки...');
        console.log('performBuy: starting for tariff', tariffId);
        const tg = window.Telegram?.WebApp;

        try {
            const formData = new FormData();
            formData.append('tariff_id', tariffId);
            formData.append('csrfmiddlewaretoken', CSRF_TOKEN);
            
            // Pass initData for secure verification
            if (tg?.initData) {
                formData.append('init_data', tg.initData);
            } else {
                // Fallback for dev
                formData.append('tg_id', userId);
                formData.append('tg_username', username);
            }

            if (replace) formData.append('replace', 'true');

            const response = await fetch('/shop/buy-api/', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                const balanceAmount = document.getElementById('profile-balance');
                if (balanceAmount) {
                    balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
                }
                window.OPTIMISTIC_HAS_SUB = true;
                if (window.syncNow) window.syncNow();
                showSuccessAnim(() => {
                    if (window.syncNow) window.syncNow();
                    showModal({
                        title: 'Успешно!',
                        message: 'Подписка успешно оформлена. Теперь вы можете подключиться к нашим серверам.',
                        icon: 'check_circle',
                        actionText: 'К подключению',
                        onAction: () => {
                            window.activateTabById('view-connection', 'Подключение');
                        }
                    });
                });
            } else if (data.error === 'insufficient_funds') {
                hideLoading();
                handleTopup(Math.ceil(data.missing_amount));
            } else {
                hideLoading();
                showModal({
                    title: 'Ошибка',
                    message: data.error || 'Произошла непредвиденная ошибка.',
                    icon: 'error',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            }
        } catch (error) {
            hideLoading();
            showModal({
                title: 'Ошибка сети',
                message: 'Не удалось связаться с сервером.',
                icon: 'cloud_off',
                actionText: 'Ок',
                onAction: hideModal
            });
        }
    }

    window.handleBuy = async (tariffId, price, tariffName = '', tariffDays = 0) => {
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;
        const username = tg?.initDataUnsafe?.user?.username || MOCK_USER_DATA?.username;

        if (!userId || userId === 'undefined') {
            showModal({
                title: 'Ошибка',
                message: 'Ваш профиль еще не загружен. Пожалуйста, попробуйте снова через секунду.',
                icon: 'hourglass_empty',
                actionText: 'Ок',
                onAction: hideModal
            });
            return;
        }

        // If user already has an active subscription — show replacement confirmation
        if (window.HAS_ACTIVE_SUB) {
            const remainingDays = window.REMAINING_DAYS || 0;
            const currentName = window.CURRENT_TARIFF_NAME || 'Текущий тариф';

            const comparisonHtml = `
                <div style="width:100%;text-align:left;display:flex;flex-direction:column;gap:10px;">
                    <div style="background:rgba(255,255,255,0.05);border-radius:14px;padding:12px 14px;">
                        <div style="font-size:10px;color:var(--md-sys-color-primary);opacity:.8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">Текущий тариф</div>
                        <div style="font-size:15px;font-weight:500;color:#E6E1E5;">${currentName}</div>
                        <div style="font-size:12px;color:rgba(230,225,229,.55);margin-top:3px;">Осталось: <b style="color:rgba(230,225,229,.85);">${remainingDays} дней</b></div>
                    </div>
                    <div style="display:flex;justify-content:center;">
                        <span class="material-symbols-rounded" style="color:var(--md-sys-color-primary);opacity:.5;font-size:20px;">arrow_downward</span>
                    </div>
                    <div style="background:rgba(208,188,255,.08);border:1px solid rgba(208,188,255,.18);border-radius:14px;padding:12px 14px;">
                        <div style="font-size:10px;color:var(--md-sys-color-primary);opacity:.8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">Новый тариф</div>
                        <div style="font-size:15px;font-weight:500;color:#E6E1E5;">${tariffName}</div>
                        <div style="font-size:12px;color:rgba(230,225,229,.55);margin-top:3px;">${tariffDays} дней &middot; ${price} ₽</div>
                    </div>
                    <div style="background:rgba(239,83,80,.08);border-radius:12px;padding:10px 12px;display:flex;gap:8px;align-items:flex-start;">
                        <span class="material-symbols-rounded" style="color:#EF5350;font-size:16px;flex-shrink:0;margin-top:1px;">warning</span>
                        <span style="font-size:12px;color:rgba(230,225,229,.75);line-height:1.5;">Оставшиеся дни <b>пропадут</b>. Подписка начнётся заново с параметрами нового тарифа.</span>
                    </div>
                </div>`;

            showModal({
                title: 'Замена подписки',
                message: '',
                icon: 'swap_horiz',
                customHtml: comparisonHtml,
                actionText: 'Заменить тариф',
                closeBtnText: 'Оставить',
                onAction: () => {
                    performBuy(tariffId, price, userId, username, true);
                }
            });
            return;
        }

        // No active sub — just buy
        performBuy(tariffId, price, userId, username, false);
    };

    window.toggleExtendMenu = () => {
        if (!window.CURRENT_TARIFF_PRICE || !window.CURRENT_TARIFF_DAYS) return;

        const basePrice = window.CURRENT_TARIFF_PRICE;
        const baseDays = window.CURRENT_TARIFF_DAYS;
        const pricePerMonth = (basePrice / baseDays) * 30;

        const options = [
            { months: 1, label: '1 месяц' },
            { months: 3, label: '3 месяца' },
            { months: 6, label: '6 месяцев' },
            { months: 12, label: '1 год' }
        ];

        let gridHtml = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; width: 100%;">';
        options.forEach(opt => {
            const optionPrice = Math.round(pricePerMonth * opt.months);
            gridHtml += `
                <button class="extend-option bounce" onclick="window.handleExtend(${opt.months}, ${optionPrice})" style="width: 100%; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); border-radius: 12px; padding: 12px; display: flex; flex-direction: column; align-items: center; gap: 4px;">
                    <span class="ext-months" style="font-size: 14px; font-weight: 500; color: #E6E1E5;">${opt.label}</span>
                    <span class="ext-price" style="font-size: 13px; color: var(--md-sys-color-primary); font-weight: 600;">${optionPrice} ₽</span>
                </button>
            `;
        });
        gridHtml += '</div>';

        showModal({
            title: 'Продление подписки',
            message: 'Выберите срок продления:',
            icon: 'update',
            customHtml: gridHtml,
            actionText: 'Отмена',
            onAction: null // Only close button needed, or action button as Cancel
        });
    };

    window.handleExtend = (months, price) => {
        showModal({
            title: 'Продление подписки',
            message: `Вы уверены, что хотите продлить подписку на ${months} мес. за ${price} ₽? Сумма будет списана с вашего баланса.`,
            icon: 'update',
            actionText: 'Продлить',
            onAction: async () => {
                hideModal();
                const tg = window.Telegram?.WebApp;
                const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

                if (!userId || userId === 'undefined') {
                    showModal({
                        title: 'Ошибка',
                        message: 'Ваш профиль еще не загружен.',
                        icon: 'error',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                    return;
                }

                showLoading('Продление подписки...');

                try {
                    const formData = new FormData();
                    formData.append('months', months);
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    } else {
                        formData.append('tg_id', userId);
                    }

                    const response = await fetch('/shop/extend-sub-api/', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok && data.success) {
                        if (window.syncNow) window.syncNow();
                        showSuccessAnim(() => {
                            const balanceAmount = document.getElementById('profile-balance');
                            if (balanceAmount) {
                                balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
                            }
                            showModal({
                                title: 'Успешно!',
                                message: `Подписка продлена на ${months} мес.`,
                                icon: 'check_circle',
                                actionText: 'Ок',
                                onAction: () => {
                                    hideModal();
                                    if (window.syncNow) window.syncNow();
                                }
                            });
                        });
                    } else if (data.error === 'insufficient_funds') {
                        hideLoading();
                        handleTopup(Math.ceil(data.missing_amount));
                    } else {
                        hideLoading();
                        showModal({
                            title: 'Ошибка',
                            message: data.error || 'Произошла непредвиденная ошибка.',
                            icon: 'error',
                            actionText: 'Ок',
                            onAction: hideModal
                        });
                    }
                } catch (error) {
                    hideLoading();
                    showModal({
                        title: 'Ошибка сети',
                        message: 'Не удалось связаться с сервером.',
                        icon: 'cloud_off',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
            }
        });
    };

    let currentSubLink = '';

    window.copySubLink = () => {
        if (!currentSubLink) return;
        const tempInput = document.createElement('input');
        tempInput.value = currentSubLink;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
        }

        showModal({
            title: 'Ссылка скопирована!',
            message: 'Ссылка для подключения успешно скопирована в буфер обмена.',
            icon: 'content_copy',
            actionText: 'Ок',
            onAction: hideModal
        });
    };

    window.openSubLink = () => {
        if (!currentSubLink) return;

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.openLink) {
            // Inside Telegram Mini App: happ:// can't be opened directly from WebView.
            // Open our server-side redirect page in the system browser via Telegram API —
            // the system browser handles the happ:// deep link correctly.
            const redirectUrl = window.location.origin
                + '/connect/open-sub/?link='
                + encodeURIComponent(currentSubLink);
            window.Telegram.WebApp.openLink(redirectUrl, { try_instant_view: false });
        } else {
            // Regular browser: direct deep link works fine
            window.location.href = 'happ://' + currentSubLink;
        }
    };

    window.handleConnect = async () => {
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

        if (!userId || userId === 'undefined') {
            showModal({
                title: 'Ошибка',
                message: 'Ваш профиль еще не загружен. Пожалуйста, подождите секунду и попробуйте снова.',
                icon: 'hourglass_empty',
                actionText: 'Ок',
                onAction: hideModal
            });
            return;
        }

        showLoading('Получение ссылки...');
        try {
            const params = new URLSearchParams();
            if (tg?.initData) {
                params.append('init_data', tg.initData);
            } else {
                params.append('tg_id', userId);
            }

            const response = await fetch(`/shop/get-sub-link-api/?${params.toString()}`);
            
            let data;
            try {
                data = await response.json();
            } catch (e) {
                throw new Error('Invalid JSON response');
            }

            if (response.ok && data.success && data.link) {
                showSuccessAnim(() => {
                    currentSubLink = data.link;
                    const btnGet = document.getElementById('btn-get-link');
                    const resultDiv = document.getElementById('connection-result');
                    const qrImg = document.getElementById('qr-code-img');

                    if (btnGet) btnGet.style.display = 'none';
                    if (resultDiv) {
                        resultDiv.style.display = 'flex';
                        qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(data.link)}`;
                    }
                });
            } else {
                hideLoading();
                showModal({
                    title: 'Ошибка',
                    message: data.error || 'У вас нет активной подписки.',
                    icon: 'error',
                    actionText: 'Ок',
                    onAction: hideModal
                });
            }
        } catch (error) {
            console.error('handleConnect error:', error);
            hideLoading();
            showModal({
                title: 'Ошибка',
                message: 'Не удалось получить ссылку. Проверьте интернет-соединение или попробуйте позже.',
                icon: 'cloud_off',
                actionText: 'Ок',
                onAction: hideModal
            });
        }
    };

    window.handleSetNodeStatus = (nodeId, nodeDataStr) => {
        const node = JSON.parse(decodeURIComponent(nodeDataStr));
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

        if (!userId || userId === 'undefined') {
            alert('Профиль не загружен');
            return;
        }

        const customHtml = `
            <div style="display: flex; flex-direction: column; gap: 12px; margin-top: 15px; text-align: left;">
                <label class="bounce" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: rgba(255,255,255,0.05); border-radius: 16px; cursor: pointer;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span class="material-symbols-rounded" style="color: var(--md-sys-color-primary);">tune</span>
                        <span style="font-size: 14px; font-weight: 500;">Ручное управление</span>
                    </div>
                    <div class="switch-ui">
                        <input type="checkbox" id="modal-use-manual" ${node.use_manual_status ? 'checked' : ''} style="display: none;">
                        <span class="slider round"></span>
                    </div>
                </label>
                
                <label id="manual-online-wrapper" class="bounce" style="display: ${node.use_manual_status ? 'flex' : 'none'}; align-items: center; justify-content: space-between; padding: 12px 16px; background: rgba(255,255,255,0.05); border-radius: 16px; cursor: pointer;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span class="material-symbols-rounded" id="manual-online-icon" style="color: ${node.manual_is_online ? '#4CAF50' : '#F44336'};">
                            ${node.manual_is_online ? 'cloud_done' : 'cloud_off'}
                        </span>
                        <span style="font-size: 14px; font-weight: 500;" id="manual-online-text">
                            ${node.manual_is_online ? 'Статус: ОНЛАЙН' : 'Статус: ОФФЛАЙН'}
                        </span>
                    </div>
                    <div class="switch-ui">
                        <input type="checkbox" id="modal-manual-online" ${node.manual_is_online ? 'checked' : ''} style="display: none;">
                        <span class="slider round"></span>
                    </div>
                </label>
            </div>
            <style>
                .switch-ui { position: relative; display: inline-block; width: 40px; height: 22px; pointer-events: none; }
                .slider { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(255,255,255,0.1); transition: .4s; border-radius: 34px; }
                .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
                input:checked + .slider { background-color: var(--md-sys-color-primary); }
                input:checked + .slider:before { transform: translateX(18px); }
            </style>
        `;

        showModal({
            title: 'Статус сервера',
            message: `Настройте параметры ноды #${nodeId}:`,
            icon: 'dns',
            actionText: 'Сохранить',
            showInput: true,
            inputValue: node.custom_status || '',
            inputPlaceholder: 'Кастомный текст статуса...',
            customHtml: customHtml,
            onAction: async () => {
                const statusText = modalAmountInput.value;
                const useManual = document.getElementById('modal-use-manual').checked;
                const manualOnline = document.getElementById('modal-manual-online').checked;

                try {
                    const formData = new FormData();
                    formData.append('node_id', nodeId);
                    formData.append('status_text', statusText);
                    formData.append('use_manual_status', useManual);
                    formData.append('manual_is_online', manualOnline);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    } else {
                        formData.append('tg_id', userId);
                    }

                    const response = await fetch('/connect/set-node-status-api/', {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        if (window.syncNow) window.syncNow();
                    } else {
                        alert('Ошибка сохранения статуса');
                    }
                } catch (e) {
                    console.error('Failed to set node status:', e);
                }
            }
        });

        // Event listeners for switches
        const useManualCheck = document.getElementById('modal-use-manual');
        const manualOnlineCheck = document.getElementById('modal-manual-online');
        const manualOnlineWrapper = document.getElementById('manual-online-wrapper');
        const onlineIcon = document.getElementById('manual-online-icon');
        const onlineText = document.getElementById('manual-online-text');

        if (useManualCheck) {
            useManualCheck.onchange = (e) => {
                manualOnlineWrapper.style.display = e.target.checked ? 'flex' : 'none';
            };
        }
        
        if (manualOnlineCheck) {
            manualOnlineCheck.onchange = (e) => {
                const isOnline = e.target.checked;
                onlineIcon.style.color = isOnline ? '#4CAF50' : '#F44336';
                onlineIcon.textContent = isOnline ? 'cloud_done' : 'cloud_off';
                onlineText.textContent = isOnline ? 'Статус: ОНЛАЙН' : 'Статус: ОФФЛАЙН';
            };
        }
    };

    window.handleBuySlot = async () => {
        const tg = window.Telegram?.WebApp;
        const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

        if (!userId || userId === 'undefined') {
            showModal({
                title: 'Ошибка',
                message: 'Ваш профиль еще не загружен.',
                icon: 'error',
                actionText: 'Ок',
                onAction: hideModal
            });
            return;
        }

        showModal({
            title: 'Купить доп. слот',
            message: 'Вы уверены, что хотите купить дополнительный слот для устройства за 100 ₽?',
            icon: 'person_add',
            actionText: 'Подтвердить',
            onAction: async () => {
                showLoading('Покупка слота...');
                try {
                    const formData = new FormData();
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    } else {
                        formData.append('tg_id', userId);
                    }

                    const response = await fetch('/shop/buy-slot-api/', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok) {
                        const balanceAmount = document.getElementById('profile-balance');
                        if (balanceAmount) {
                            balanceAmount.textContent = `${data.new_balance.toFixed(0)} ₽`;
                        }
                        if (window.syncNow) window.syncNow();
                        showSuccessAnim(() => {
                            if (window.syncNow) window.syncNow();
                        });
                    } else if (data.error === 'insufficient_funds') {
                        hideLoading();
                        handleTopup(Math.ceil(data.missing_amount));
                    } else {
                        hideLoading();
                        showModal({
                            title: 'Ошибка',
                            message: data.error || 'Ошибка покупки слота.',
                            icon: 'error',
                            actionText: 'Ок',
                            onAction: hideModal
                        });
                    }
                } catch (e) {
                    hideLoading();
                    showModal({
                        title: 'Ошибка сети',
                        message: 'Не удалось связаться с сервером.',
                        icon: 'cloud_off',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
            }
        });
    };

    window.handleDeleteDevice = (hwid, rowIndex) => {
        showModal({
            title: 'Удалить устройство?',
            message: 'Это устройство будет удалено из вашего списка. При следующем подключении оно снова зарегистрируется автоматически.',
            icon: 'delete_outline',
            actionText: 'Удалить',
            onAction: async () => {
                hideModal();
                const tg = window.Telegram?.WebApp;
                const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;

                if (!userId || userId === 'undefined') {
                    showModal({
                        title: 'Ошибка',
                        message: 'Ваш профиль еще не загружен.',
                        icon: 'error',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                    return;
                }

                showLoading('Удаление устройства...');

                try {
                    const formData = new FormData();
                    formData.append('hwid', hwid);
                    formData.append('csrfmiddlewaretoken', CSRF_TOKEN);

                    if (tg?.initData) {
                        formData.append('init_data', tg.initData);
                    } else {
                        formData.append('tg_id', userId);
                    }

                    const response = await fetch('/shop/delete-hwid-device-api/', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok && data.success) {
                        hideLoading();
                        if (window.syncNow) window.syncNow();
                        // Animate row out
                        const row = document.getElementById(`device-row-${rowIndex}`);
                        if (row) {
                            row.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                            row.style.opacity = '0';
                            row.style.transform = 'translateX(20px)';
                            // Remove adjacent divider
                            const next = row.nextElementSibling;
                            const prev = row.previousElementSibling;
                            const divider = (next && next.classList.contains('settings-divider')) ? next
                                : (prev && prev.classList.contains('settings-divider')) ? prev : null;
                            setTimeout(() => {
                                row.remove();
                                if (divider) divider.remove();
                                // If block is now empty, show empty state
                                const block = document.querySelector('#view-settings .settings-block');
                                if (block && block.querySelectorAll('.device-row').length === 0) {
                                    block.innerHTML = `
                                        <div class="settings-empty">
                                            <span class="material-symbols-rounded">devices_off</span>
                                            <span>Нет подключённых устройств</span>
                                        </div>`;
                                }
                            }, 350);
                        }
                    } else {
                        hideLoading();
                        showModal({
                            title: 'Ошибка',
                            message: data.error || 'Не удалось удалить устройство.',
                            icon: 'error',
                            actionText: 'Ок',
                            onAction: hideModal
                        });
                    }
                } catch (e) {
                    hideLoading();
                    showModal({
                        title: 'Ошибка сети',
                        message: 'Не удалось связаться с сервером.',
                        icon: 'cloud_off',
                        actionText: 'Ок',
                        onAction: hideModal
                    });
                }
            }
        });
    };

    window.handleProxyConnect = (url, name) => {
        if (!url) return;

        showModal({
            title: 'Telegram Прокси',
            message: `Вы собираетесь подключить прокси "${name}". Это позволит Telegram работать стабильнее в условиях ограничений.`,
            icon: 'send',
            actionText: 'Подключить',
            onAction: () => {
                if (window.Telegram && window.Telegram.WebApp) {
                    if (url.includes('t.me/') || url.startsWith('tg://')) {
                        window.Telegram.WebApp.openTelegramLink(url);
                    } else {
                        window.Telegram.WebApp.openLink(url);
                    }
                } else {
                    window.open(url, '_blank');
                }
            }
        });
    };

    window.copyProxyLink = (url) => {
        if (!url) return;
        const tempInput = document.createElement('input');
        tempInput.value = url;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
        }

        showModal({
            title: 'Ссылка скопирована!',
            message: 'Ссылка на прокси успешно скопирована.',
            icon: 'content_copy',
            actionText: 'Ок',
            onAction: hideModal
        });
    };

    // Data Synchronization Logic
    function updateUIWithSyncData(data) {
        if (!data.success) return;

        // Update Balance and Profile Details
        if (data.profile) {
            const balanceEl = document.getElementById('profile-balance');
            if (balanceEl) balanceEl.textContent = `${data.profile.balance.toFixed(0)} ₽`;
            
            const tarifNameEl = document.getElementById('profile-tarif-name');
            if (tarifNameEl) tarifNameEl.textContent = data.profile.tarif_name;

            // Update global tariff variables for Extension menu
            if (data.profile.tarif_price) window.CURRENT_TARIFF_PRICE = data.profile.tarif_price;
            if (data.profile.tarif_days) window.CURRENT_TARIFF_DAYS = data.profile.tarif_days;

            // Update HAS_ACTIVE_SUB flag
            // Use OR with OPTIMISTIC_HAS_SUB to avoid flickering right after purchase
            window.HAS_ACTIVE_SUB = !!data.rw_user || !!window.OPTIMISTIC_HAS_SUB;
            if (data.rw_user) {
                window.CURRENT_TARIFF_NAME = data.profile.tarif_name;
                window.OPTIMISTIC_HAS_SUB = false; // Reset once we have real data from Remnawave
            }
        }

        // Update Proxy
        const proxyContainer = document.getElementById('proxy-container');
        if (proxyContainer) {
            if (data.proxies && data.proxies.length > 0) {
                let proxiesHtml = '';
                data.proxies.forEach(proxy => {
                    proxiesHtml += `
                    <div class="proxy-section" style="margin-top: 10px; padding: 18px; background: var(--panel-bg); border-radius: 24px; position: relative; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);">
                        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 16px; position: relative; z-index: 1;">
                            <div style="width: 44px; height: 44px; border-radius: 14px; background: rgba(208, 188, 255, 0.08); color: var(--md-sys-color-primary); display: flex; align-items: center; justify-content: center;">
                                <span class="material-symbols-rounded" style="font-size: 24px;">send</span>
                            </div>
                            <div style="flex: 1;">
                                <div style="display: flex; align-items: center; gap: 6px;">
                                    <h4 style="margin: 0; font-size: 15px; font-weight: 500; color: #FFFFFF;">${proxy.name}</h4>
                                </div>
                                <span style="font-size: 12px; opacity: 0.5; color: #E6E1E5; display: block; margin-top: 2px;">Обход ограничений (Прокси)</span>
                            </div>
                        </div>
                        
                        <div style="display: flex; gap: 10px; position: relative; z-index: 1;">
                            <button class="action-btn bounce" 
                                    style="flex: 1; height: 48px; background: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary); border-radius: 14px; font-weight: 600; font-size: 14px;" 
                                    onclick="handleProxyConnect('${proxy.connection_url}', '${proxy.name}')">
                                <span class="material-symbols-rounded" style="font-size: 20px;">bolt</span>
                                Подключить
                            </button>
                            <button class="action-btn bounce" 
                                    style="width: 48px; height: 48px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; display: flex; align-items: center; justify-content: center; padding: 0;" 
                                    onclick="copyProxyLink('${proxy.connection_url}')"
                                    title="Скопировать ссылку">
                                <span class="material-symbols-rounded" style="font-size: 20px; color: #FFFFFF; opacity: 0.7;">content_copy</span>
                            </button>
                        </div>
                    </div>`;
                });
                proxyContainer.innerHTML = proxiesHtml;
            } else {
                proxyContainer.innerHTML = '';
            }
        }

        // Update Subscription Card in Tariffs View
        const subContainer = document.getElementById('current-subscription-container');
        if (subContainer) {
            if (data.rw_user && data.profile) {
                const remDays = data.rw_user.remaining_days || 0;
                subContainer.innerHTML = `
                    <div class=" bounce">
                        <div class="sub-header">
                            <div class="sub-icon">
                                <span class="material-symbols-rounded">verified_user</span>
                            </div>
                            <div class="sub-info">
                                <span class="sub-label">Текущая подписка</span>
                                <h3 class="sub-title" id="sub-title-display">${data.profile.tarif_name}</h3>
                            </div>
                        </div>
                        <div class="sub-footer" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div class="sub-stat">
                                <span class="material-symbols-rounded">timer</span>
                                <span id="sub-remaining-days-display">Осталось дней: ${remDays}</span>
                            </div>
                            <button class="action-btn bounce" style="padding: 6px 12px; font-size: 13px; background: rgba(208, 188, 255, 0.15); color: var(--md-sys-color-primary); white-space: nowrap; flex: 0 0 auto;" onclick="toggleExtendMenu()">
                                <span class="material-symbols-rounded" style="font-size: 16px; margin-right: 4px;">update</span>Продлить
                            </button>
                        </div>
                    </div>`;
                window.REMAINING_DAYS = remDays;
            } else {
                subContainer.innerHTML = '';
            }
        }

        // Update Connection View Status
        const connectionSubInfo = document.querySelector('#view-connection .subscription-info');
        if (connectionSubInfo && data.profile) {
            const daysEl = document.getElementById('connection-remaining-days');
            const getBtn = document.getElementById('btn-get-link');
            const resultEl = document.getElementById('connection-result');
            
            const wasActive = !!getBtn;
            const isActive = !!data.rw_user;

            if (wasActive !== isActive) {
                // Redraw everything only if status changed
                const username = document.getElementById('connection-username')?.textContent || `@${tg?.initDataUnsafe?.user?.username || MOCK_USER_DATA?.username || 'user'}`;
                let connHtml = `
                    <div class="info-item">
                        <span class="label">Пользователь</span>
                        <span class="value" id="connection-username">${username}</span>
                    </div>`;
                
                if (isActive) {
                    connHtml += `
                        <div class="info-item">
                            <span class="label">Статус</span>
                            <span class="value" style="color: #4CAF50;">Активен</span>
                        </div>
                        <div class="info-item">
                            <span class="label">Осталось времени</span>
                            <span class="value" id="connection-remaining-days">${data.rw_user.remaining_days} дней</span>
                        </div>
                        <button id="btn-get-link" class="action-btn bounce" style="margin-top: 16px; background-color: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary);" onclick="handleConnect()">
                            <span class="material-symbols-rounded">link</span>
                            Получить ссылку для подключения
                        </button>
                        <div id="connection-result" style="display: none; margin-top: 16px; flex-direction: column; align-items: center; gap: 16px; padding: 16px; background: rgba(255,255,255,0.05); border-radius: 16px;">
                            <span style="font-size: 14px; color: var(--panel-icon); text-align: center;">Отсканируйте QR-код или скопируйте ссылку для настройки вашего VPN-клиента</span>
                            <img id="qr-code-img" src="" alt="QR Code" style="width: 160px; height: 160px; border-radius: 12px; background: white; padding: 8px;">
                            <div style="display: flex; gap: 8px; width: 100%;">
                                <button class="action-btn bounce" style="flex: 1; padding: 12px; font-size: 14px; background-color: rgba(255,255,255,0.1);" onclick="copySubLink()">
                                    <span class="material-symbols-rounded" style="font-size: 20px;">content_copy</span>
                                    Скопировать
                                </button>
                                <button class="action-btn bounce" style="flex: 1; padding: 12px; font-size: 14px; background-color: var(--md-sys-color-primary); color: var(--md-sys-color-on-primary);" onclick="showInstructions()">
                                    <span class="material-symbols-rounded" style="font-size: 20px;">open_in_new</span>
                                    Подключить
                                </button>
                            </div>
                        </div>`;
                } else {
                    connHtml += `
                        <button class="action-btn bounce" style="margin-top: 16px; opacity: 0.5;" disabled>
                            <span class="material-symbols-rounded">link_off</span>
                            Нет активной подписки
                        </button>`;
                }
                connectionSubInfo.innerHTML = connHtml;
            } else if (isActive) {
                // If already active, just update the values without touching the rest of DOM
                if (daysEl) daysEl.textContent = `${data.rw_user.remaining_days} дней`;
            }
        }

        // Update Tariff Cards (Owned status)
        if (data.profile && data.profile.tarif_name) {
            document.querySelectorAll('.tariff-card-v2').forEach(card => {
                const title = card.querySelector('h3').textContent;
                const btn = card.querySelector('.v2-buy-btn');
                if (btn) {
                    if (title === data.profile.tarif_name) {
                        btn.textContent = 'Уже активен';
                        btn.classList.add('owned');
                        btn.disabled = true;
                        btn.onclick = null;
                    } else {
                        btn.textContent = 'Купить';
                        btn.classList.remove('owned');
                        btn.disabled = false;
                        // The original onclick is preserved if we don't overwrite it, 
                        // but since we are doing this dynamically, we should ensure it's correct.
                        // Actually, it's better to not touch it if it's not the owned one.
                    }
                }
            });
        }

        // Update Remaining Days (Sync secondary displays)
        if (data.rw_user) {
            const remDays = data.rw_user.remaining_days || 0;
            const subRemDaysDisplay = document.getElementById('sub-remaining-days-display');
            const connRemDaysDisplay = document.getElementById('connection-remaining-days');
            
            if (subRemDaysDisplay) subRemDaysDisplay.textContent = `Осталось дней: ${remDays}`;
            if (connRemDaysDisplay) connRemDaysDisplay.textContent = `${remDays} дней`;
            
            window.REMAINING_DAYS = remDays;
        }

        // Update Nodes (Server Status)
        const onlineCountEl = document.getElementById('online-count-display');
        const offlineCountEl = document.getElementById('offline-count-display');
        if (onlineCountEl && data.online_count !== undefined) onlineCountEl.textContent = `${data.online_count} онлайн`;
        if (offlineCountEl && data.offline_count !== undefined) offlineCountEl.textContent = `${data.offline_count} недоступно`;

        const nodesContainer = document.getElementById('nodes-list-container');
        if (nodesContainer && data.nodes) {
            // Only update nodes UI if we have data OR if the empty list is not an error
            if (data.nodes.length > 0 || !data.nodes_error) {
                let nodesHtml = '';
                data.nodes.forEach(node => {
                    let isOnline = node.isConnected;
                    let statusText = isOnline ? 'Доступно' : 'Недоступно';
                    let statusColor = isOnline ? '#4CAF50' : '#F44336';

                    if (node.use_manual_status) {
                        isOnline = node.manual_is_online;
                        statusText = node.custom_status || (isOnline ? 'Доступно' : 'Недоступно');
                        statusColor = isOnline ? '#4CAF50' : '#F44336';
                        if (node.custom_status) statusColor = '#BB86FC';
                    } else if (node.custom_status) {
                        statusText = node.custom_status;
                        statusColor = '#BB86FC';
                    }

                    const nodeJson = encodeURIComponent(JSON.stringify(node));

                    nodesHtml += `
                        <div class="server-selector bounce" style="margin-top: 10px;"
                             ${data.is_admin ? `onclick="handleSetNodeStatus('${node.id}', '${nodeJson}')"` : ''}>
                            <div class="server-info">
                                <div class="server-icon-wrapper">
                                    ${node.countryCode ? `
                                        <img src="https://flagcdn.com/w80/${node.countryCode.toLowerCase()}.png" 
                                             class="flag-img" 
                                             alt="${node.countryCode}">
                                    ` : `
                                        <span class="material-symbols-rounded">
                                            ${node.isConnected ? 'lan' : 'lan_off'}
                                        </span>
                                    `}
                                </div>
                                <div class="server-details">
                                    <span class="server-name">${node.display_name}</span>
                                    <span class="server-ping">
                                        <span style="color: ${statusColor}; font-weight: 500;">${statusText}</span>
                                    </span>
                                </div>
                            </div>
                            ${data.is_admin ? '<span class="material-symbols-rounded" style="opacity: 0.3; font-size: 20px;">chevron_right</span>' : ''}
                        </div>`;
                });
                nodesContainer.innerHTML = nodesHtml;
            } else {
                console.warn('Sync nodes error or empty while error flag set, keeping previous list');
            }
        }

        // Update Devices
        const deviceCountEl = document.getElementById('devices-count-display');
        if (deviceCountEl && data.rw_user) {
            deviceCountEl.innerHTML = `
                <span class="material-symbols-rounded" style="font-size: 14px;">devices</span>
                ${data.hwid_devices.length} / ${data.rw_user.hwidDeviceLimit || 0}
            `;
        }

        const devicesContainer = document.getElementById('devices-list-container');
        if (devicesContainer && data.hwid_devices) {
            if (data.hwid_devices.length === 0) {
                devicesContainer.innerHTML = `
                    <div class="settings-empty">
                        <span class="material-symbols-rounded">devices_off</span>
                        <span>Нет подключённых устройств</span>
                    </div>`;
            } else {
                let devicesHtml = '';
                data.hwid_devices.forEach((device, index) => {
                    const idx = index + 1;
                    let icon = 'devices';
                    if (device.platform === 'Android') icon = 'smartphone';
                    else if (device.platform === 'Windows') icon = 'computer';
                    else if (device.platform === 'iOS') icon = 'phone_iphone';
                    else if (device.platform === 'macOS') icon = 'laptop_mac';
                    else if (device.platform === 'Linux') icon = 'terminal';

                    devicesHtml += `
                        <div class="device-row" id="device-row-${idx}">
                            <div class="device-row-icon">
                                <span class="material-symbols-rounded">${icon}</span>
                            </div>
                            <div class="device-row-info">
                                <span class="device-row-name">${device.deviceModel || "Неизвестное устройство"}</span>
                                <span class="device-row-meta">${device.platform || "—"} · ${device.hwid.substring(0, 14)}...</span>
                            </div>
                            <button class="device-delete-btn bounce"
                                    onclick="handleDeleteDevice('${device.hwid}', ${idx})"
                                    title="Удалить устройство">
                                <span class="material-symbols-rounded">delete_outline</span>
                            </button>
                        </div>
                        ${index < data.hwid_devices.length - 1 ? '<div class="settings-divider"></div>' : ''}`;
                });
                devicesContainer.innerHTML = devicesHtml;
            }
        }
        
        // Update Slot Purchase Section
        const slotContainer = document.getElementById('slot-purchase-container');
        if (slotContainer) {
            if (data.rw_user) {
                slotContainer.innerHTML = `
                    <div class="settings-section">
                        <div class="settings-section-header">
                            <span class="settings-section-label">Слоты устройств</span>
                        </div>
                        <div class="settings-block">
                            <div class="slot-info-row">
                                <div class="slot-info-icon">
                                    <span class="material-symbols-rounded">add_circle</span>
                                </div>
                                <div class="slot-info-text">
                                    <span class="slot-info-title">Дополнительный слот</span>
                                    <span class="slot-info-sub">Подключите ещё одно устройство</span>
                                </div>
                                <button class="slot-buy-btn bounce" onclick="handleBuySlot()">
                                    100 ₽
                                </button>
                            </div>
                        </div>
                    </div>`;
            } else {
                slotContainer.innerHTML = '';
            }
        }

        // Update Payment History
        const historyContainer = document.getElementById('history-list-container');
        if (historyContainer && data.payments) {
            if (data.payments.length === 0) {
                historyContainer.innerHTML = `
                    <div style="display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px 20px; opacity: 0.4; text-align: center;">
                        <span class="material-symbols-rounded" style="font-size: 48px;">receipt_long</span>
                        <span>История платежей пока пуста</span>
                    </div>`;
            } else {
                let historyHtml = '';
                data.payments.forEach(payment => {
                    const isTopup = payment.order_type === 'TOPUP';
                    const isPaid = payment.status === 'PAID';
                    historyHtml += `
                        <div class="history-item" style="background: var(--panel-bg); border-radius: 20px; padding: 16px; display: flex; align-items: center; gap: 16px;">
                            <div style="width: 44px; height: 44px; border-radius: 14px; background: ${isTopup ? 'rgba(76, 175, 80, 0.1)' : 'rgba(255, 255, 255, 0.05)'}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                                <span class="material-symbols-rounded" style="color: ${isTopup ? '#4CAF50' : '#FFFFFF'}; font-size: 24px; opacity: 0.8;">
                                    ${isTopup ? 'account_balance_wallet' : 'shopping_bag'}
                                </span>
                            </div>
                            <div style="flex: 1;">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2px;">
                                    <span style="font-weight: 500; font-size: 15px;">
                                        ${isTopup ? 'Пополнение баланса' : (payment.tariff_name || "Покупка тарифа")}
                                    </span>
                                    <span style="font-weight: 600; font-size: 15px; color: ${isTopup ? '#4CAF50' : '#FFFFFF'};">
                                        ${isTopup ? '+' : '-'}${payment.amount.toFixed(0)} ₽
                                    </span>
                                </div>
                                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 12px; opacity: 0.5;">
                                    <span>${payment.created_at}</span>
                                    <span style="color: ${isPaid ? '#4CAF50' : '#EF5350'}; opacity: 0.8;">
                                        ${isPaid ? 'Успешно' : 'Ошибка'}
                                    </span>
                                </div>
                            </div>
                        </div>`;
                });
                historyContainer.innerHTML = historyHtml;
            }
        }
    }

    async function startDataSync() {
        const tg = window.Telegram?.WebApp;
        
        window.syncNow = async () => {
            const userId = tg?.initDataUnsafe?.user?.id || MOCK_USER_DATA?.id;
            if (!userId || userId === 'undefined') {
                console.warn('Sync skipped: userId not ready');
                return;
            }

            let url = `/shop/sync-data-api/`;
            const params = new URLSearchParams();
            
            if (tg?.initData) {
                params.append('init_data', tg.initData);
            } else {
                params.append('tg_id', userId);
            }
            
            try {
                const response = await fetch(`${url}?${params.toString()}`);
                if (response.ok) {
                    const data = await response.json();
                    updateUIWithSyncData(data);
                }
            } catch (e) {
                console.error('Manual sync failed:', e);
            }
        };

        // Poll every 5 seconds
        setInterval(window.syncNow, 5000);
        
        // Initial sync attempt
        window.syncNow();
    }

    // --- Instruction Carousel Logic ---
    let currentInstrSlide = 0;
    const totalInstrSlides = 4;
    
    let galleriesInitialized = false;
    
    function initInstructionGalleries() {
        if (galleriesInitialized) return;
        galleriesInitialized = true;
        
        const galleries = document.querySelectorAll('.instruction-images');
        galleries.forEach(gallery => {
            let isDown = false;
            let startX;
            let scrollLeft;
            let hasDragged = false; // track if real drag happened (to block click)

            // Prevent native image drag inside gallery
            gallery.querySelectorAll('img').forEach(img => {
                img.setAttribute('draggable', 'false');
                img.addEventListener('dragstart', e => e.preventDefault());
            });

            gallery.addEventListener('mousedown', (e) => {
                isDown = true;
                hasDragged = false;
                gallery.classList.add('dragging');
                startX = e.pageX - gallery.offsetLeft;
                scrollLeft = gallery.scrollLeft;
                e.preventDefault(); // prevent text/image selection
            });

            gallery.addEventListener('mouseleave', () => {
                if (!isDown) return;
                isDown = false;
                gallery.classList.remove('dragging');
                gallery.style.scrollSnapType = 'x mandatory';
            });

            gallery.addEventListener('mouseup', () => {
                isDown = false;
                gallery.classList.remove('dragging');
                gallery.style.scrollSnapType = 'x mandatory';
            });

            gallery.addEventListener('mousemove', (e) => {
                if (!isDown) return;
                e.preventDefault();
                const x = e.pageX - gallery.offsetLeft;
                const delta = x - startX;
                // Only disable snap once actual drag starts (threshold 5px)
                if (Math.abs(delta) > 5) {
                    hasDragged = true;
                    gallery.style.scrollSnapType = 'none';
                }
                gallery.scrollLeft = scrollLeft - delta;
            });

            // Block click on images if we actually dragged
            gallery.addEventListener('click', (e) => {
                if (hasDragged) e.stopPropagation();
            }, true);

            gallery.style.cursor = 'grab';
            gallery.style.userSelect = 'none';
            
            // Dot updates on scroll
            gallery.addEventListener('scroll', () => {
                const images = gallery.querySelectorAll('img');
                if (images.length === 0) return;
                const imageWidth = gallery.clientWidth * 0.9;
                let activeIndex = Math.round(gallery.scrollLeft / imageWidth);
                if (activeIndex < 0) activeIndex = 0;
                if (activeIndex >= images.length) activeIndex = images.length - 1;
                
                const dotsContainer = gallery.nextElementSibling;
                if (dotsContainer && dotsContainer.classList.contains('gallery-dots')) {
                    dotsContainer.querySelectorAll('.dot').forEach((dot, idx) => {
                        dot.classList.toggle('active', idx === activeIndex);
                    });
                }
            });
        });

        // Drag-to-swipe for the main carousel track on PC
        const track = document.getElementById('instruction-track');
        const container = track ? track.parentElement : null;
        if (track && container) {
            let trackDown = false;
            let trackStartX;
            let trackDragged = false;

            container.addEventListener('mousedown', (e) => {
                // Only start if not inside a gallery
                if (e.target.closest('.instruction-images')) return;
                trackDown = true;
                trackDragged = false;
                trackStartX = e.pageX;
                e.preventDefault();
            });

            window.addEventListener('mouseup', () => {
                if (!trackDown) return;
                trackDown = false;
            });

            window.addEventListener('mousemove', (e) => {
                if (!trackDown) return;
                const delta = e.pageX - trackStartX;
                if (Math.abs(delta) > 30) {
                    trackDragged = true;
                    trackDown = false;
                    if (delta < 0) {
                        window.nextInstructionSlide();
                    } else {
                        window.prevInstructionSlide();
                    }
                }
            });

            // Block click events that follow a drag
            container.addEventListener('click', (e) => {
                if (trackDragged) {
                    e.stopPropagation();
                    trackDragged = false;
                }
            }, true);
        }
    }

    window.showInstructions = () => {
        const overlay = document.getElementById('instruction-overlay');
        if (overlay) {
            // Move to body to prevent transform containment issues on mobile
            if (overlay.parentElement !== document.body) {
                document.body.appendChild(overlay);
            }

            // Reset slide BEFORE making overlay visible to avoid
            // accidental clicks on slide-4's openSubLink() button
            currentInstrSlide = 0;
            updateInstructionCarousel();

            overlay.style.display = 'flex';
            // Temporarily block pointer events on slides during open animation
            const track = document.getElementById('instruction-track');
            if (track) {
                track.style.pointerEvents = 'none';
                setTimeout(() => { track.style.pointerEvents = ''; }, 350);
            }
            // Force reflow
            void overlay.offsetWidth;
            overlay.classList.add('active');

            initInstructionGalleries();
            try {
                detectAndHighlightPlatform();
            } catch (e) { console.error(e); }
        }
    };
    
    window.downloadHiddify = (platform) => {
        let url = 'https://happ.su/';
        if (platform === 'ios' || platform === 'mac') {
            url = 'https://apps.apple.com/us/app/happ-proxy-utility/id6504287215';
        } else if (platform === 'android') {
            url = 'https://play.google.com/store/apps/details?id=com.happproxy';
        } else if (platform === 'windows') {
            url = 'https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe';
        }
        
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.openLink(url);
        } else {
            window.open(url, '_blank');
        }
    };

    function detectAndHighlightPlatform() {
        let platform = 'unknown';
        const tgPlatform = window.Telegram?.WebApp?.platform;
        
        if (tgPlatform) {
            if (tgPlatform === 'android') platform = 'android';
            else if (tgPlatform === 'ios') platform = 'ios';
            else if (tgPlatform === 'macos' || tgPlatform === 'mac') platform = 'mac';
            else if (tgPlatform === 'windows' || tgPlatform === 'tdesktop') platform = 'windows';
        }
        
        if (platform === 'unknown') {
            const ua = navigator.userAgent.toLowerCase();
            if (/android/.test(ua)) platform = 'android';
            else if (/iphone|ipad|ipod/.test(ua)) platform = 'ios';
            else if (/mac/.test(ua)) platform = 'mac';
            else if (/win/.test(ua)) platform = 'windows';
        }
        
        document.querySelectorAll('.platform-btn').forEach(btn => {
            btn.classList.remove('recommended');
            const btnPlatform = btn.getAttribute('data-platform');
            if (btnPlatform === platform || (btnPlatform === 'ios' && platform === 'mac')) {
                btn.classList.add('recommended');
            }
        });
    }

    window.closeInstructions = () => {
        const overlay = document.getElementById('instruction-overlay');
        if (overlay) {
            overlay.classList.remove('active');
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 300); // match transition duration
        }
    };
    
    window.nextInstructionSlide = () => {
        if (currentInstrSlide < totalInstrSlides - 1) {
            currentInstrSlide++;
            updateInstructionCarousel();
        }
    };
    
    window.skipToLastSlide = () => {
        currentInstrSlide = totalInstrSlides - 1;
        updateInstructionCarousel();
    };
    
    window.prevInstructionSlide = () => {
        if (currentInstrSlide > 0) {
            currentInstrSlide--;
            updateInstructionCarousel();
        }
    };
    
    function updateInstructionCarousel() {
        const track = document.getElementById('instruction-track');
        const dots = document.querySelectorAll('#carousel-dots .dot');
        const prevBtn = document.getElementById('instr-prev-btn');
        const nextBtn = document.getElementById('instr-next-btn');
        const skipBtn = document.getElementById('instr-skip-btn');
        
        if (track) {
            track.style.transform = `translateX(-${currentInstrSlide * 25}%)`;
        }
        
        if (dots) {
            dots.forEach((dot, index) => {
                dot.classList.toggle('active', index === currentInstrSlide);
            });
        }
        
        if (prevBtn) {
            prevBtn.style.visibility = currentInstrSlide === 0 ? 'hidden' : 'visible';
        }
        
        if (skipBtn) {
            skipBtn.style.display = currentInstrSlide === totalInstrSlides - 1 ? 'none' : 'block';
        }
        
        if (nextBtn) {
            if (currentInstrSlide === totalInstrSlides - 1) {
                nextBtn.style.display = 'none';
            } else {
                nextBtn.style.display = 'block';
                
                if (currentInstrSlide === 0) {
                    nextBtn.innerText = 'Далее';
                    nextBtn.style.opacity = '1';
                    nextBtn.disabled = false;
                } else {
                    nextBtn.innerText = 'Я всё выполнил';
                    
                    const currentSlideElement = document.querySelectorAll('.carousel-slide')[currentInstrSlide];
                    const gallery = currentSlideElement.querySelector('.instruction-images');
                    
                    if (gallery) {
                        const checkScroll = () => {
                            if (gallery.clientWidth > 0 && gallery.scrollLeft + gallery.clientWidth >= gallery.scrollWidth - 10) {
                                return true;
                            }
                            return false;
                        };
                        
                        if (checkScroll() || gallery.dataset.scrolledToEnd === 'true') {
                            nextBtn.style.opacity = '1';
                            nextBtn.disabled = false;
                        } else {
                            nextBtn.style.opacity = '0.3';
                            nextBtn.disabled = true;
                            
                            if (!gallery.dataset.hasScrollListener) {
                                gallery.dataset.hasScrollListener = 'true';
                                gallery.addEventListener('scroll', () => {
                                    if (checkScroll()) {
                                        gallery.dataset.scrolledToEnd = 'true';
                                        // Update button if we are still on this slide
                                        const slides = Array.from(document.querySelectorAll('.carousel-slide'));
                                        if (currentInstrSlide === slides.indexOf(currentSlideElement)) {
                                            nextBtn.style.opacity = '1';
                                            nextBtn.disabled = false;
                                        }
                                    }
                                });
                            }
                        }
                    } else {
                        nextBtn.style.opacity = '1';
                        nextBtn.disabled = false;
                    }
                }
            }
        }
    }

    startDataSync();
});
