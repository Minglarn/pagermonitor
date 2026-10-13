/**
 * Universal Theme-Aware Confirmation Dialog for PagerMonitor
 * Ensures strictly no emojis, crisp rendering without smearing, identical button geometry,
 * and seamless support for dark and light themes.
 */
(function () {
    let confirmResolve = null;

    function getOrCreateModal() {
        let modal = document.getElementById('globalConfirmModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'globalConfirmModal';
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content modal-confirm-box" role="dialog" aria-modal="true" aria-labelledby="globalConfirmTitle">
                    <div class="modal-header modal-confirm-header">
                        <div class="modal-title-row">
                            <span class="modal-icon-badge danger" id="globalConfirmIcon">
                                <i class="fas fa-trash-alt"></i>
                            </span>
                            <div>
                                <h3 id="globalConfirmTitle" class="modal-confirm-title">Confirm Action</h3>
                                <p id="globalConfirmMessage" class="modal-confirm-text">Are you sure you want to proceed?</p>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer modal-confirm-footer">
                        <button type="button" class="modal-btn modal-btn-cancel" id="globalConfirmCancelBtn">Cancel</button>
                        <button type="button" class="modal-btn modal-btn-confirm modal-btn-danger" id="globalConfirmActionBtn">Proceed</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            document.getElementById('globalConfirmCancelBtn').addEventListener('click', () => {
                closeModal(false);
            });

            document.getElementById('globalConfirmActionBtn').addEventListener('click', () => {
                closeModal(true);
            });

            // Close on background overlay click
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal(false);
                }
            });

            // Close on Escape key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && modal.classList.contains('show')) {
                    closeModal(false);
                }
            });
        }
        return modal;
    }

    function closeModal(result) {
        const modal = document.getElementById('globalConfirmModal');
        if (modal) {
            modal.classList.remove('show');
        }
        // Also close any legacy modal element if present
        const legacyModal = document.getElementById('confirmModal');
        if (legacyModal) {
            legacyModal.classList.remove('show');
        }

        if (confirmResolve) {
            const res = confirmResolve;
            confirmResolve = null;
            res(result);
        }
    }

    /**
     * Show a standardized confirmation dialog
     * @param {Object} options
     * @param {string} options.title Dialog title
     * @param {string} options.message Detailed message
     * @param {string} options.confirmText Text for confirm button (default: 'Delete')
     * @param {string} options.cancelText Text for cancel button (default: 'Cancel')
     * @param {boolean} options.isDanger True for red destructive action, false for primary accent
     * @returns {Promise<boolean>}
     */
    window.showConfirmDialog = function (options = {}) {
        const title = options.title || 'Confirm Action';
        const message = options.message || 'Are you sure you want to proceed?';
        const confirmText = options.confirmText || 'Delete';
        const cancelText = options.cancelText || 'Cancel';
        const isDanger = options.isDanger !== false;

        const modal = getOrCreateModal();
        const titleEl = document.getElementById('globalConfirmTitle');
        const msgEl = document.getElementById('globalConfirmMessage');
        const confirmBtn = document.getElementById('globalConfirmActionBtn');
        const cancelBtn = document.getElementById('globalConfirmCancelBtn');
        const iconBadge = document.getElementById('globalConfirmIcon');

        if (titleEl) titleEl.textContent = title;
        if (msgEl) msgEl.textContent = message;
        if (confirmBtn) {
            confirmBtn.textContent = confirmText;
            if (isDanger) {
                confirmBtn.className = 'modal-btn modal-btn-confirm modal-btn-danger';
            } else {
                confirmBtn.className = 'modal-btn modal-btn-confirm modal-btn-primary';
            }
        }
        if (cancelBtn) cancelBtn.textContent = cancelText;

        if (iconBadge) {
            if (isDanger) {
                iconBadge.className = 'modal-icon-badge danger';
                iconBadge.innerHTML = '<i class="fas fa-trash-alt"></i>';
            } else {
                iconBadge.className = 'modal-icon-badge info';
                iconBadge.innerHTML = '<i class="fas fa-info-circle"></i>';
            }
        }

        modal.classList.add('show');
        if (confirmBtn) confirmBtn.focus();

        return new Promise(resolve => {
            confirmResolve = resolve;
        });
    };

    /**
     * Backward-compatible shorthand helper
     */
    window.showConfirm = function (title, message, actionLabel = 'Delete') {
        const isDeleteAction = !actionLabel || /delete|ta bort|remove|purge/i.test(actionLabel);
        return window.showConfirmDialog({
            title: title,
            message: message,
            confirmText: actionLabel || 'Delete',
            isDanger: isDeleteAction
        });
    };

    window.closeConfirm = function (val) {
        closeModal(val);
    };
})();
