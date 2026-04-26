/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.TaborcataMenuRedirect = publicWidget.Widget.extend({
    selector: 'header, .o_header_affix, .o_header_standard, .navbar, .navbar-nav',

    start() {
        this._super.apply(this, arguments);

        document.addEventListener('click', (ev) => {
            let toggleElement = ev.target.closest('.o_mega_menu_toggle, .mega-menu-text-area');
            if (toggleElement) {
                const menuLabel = toggleElement.innerText.trim().toUpperCase();

                if (menuLabel.includes('DENNÉ TÁBORY') || menuLabel === 'DENNÉ TÁBORY') {
                    ev.preventDefault();
                    ev.stopPropagation();
                    ev.stopImmediatePropagation();
                    console.log('Mega: Redirecting to /denne-tabory-bratislava');
                    window.location.assign('/denne-tabory-bratislava');
                    return;
                }
            }

            let dropdownToggle = ev.target.closest('.nav-item.dropdown > .nav-link.dropdown-toggle, .nav-link.dropdown-toggle');
            if (dropdownToggle) {
                // Skip if it's already handled as mega
                if (dropdownToggle.closest('.o_mega_menu_toggle')) return;

                const menuLabel = dropdownToggle.innerText.trim().toUpperCase();

                if (menuLabel.includes('POBYTOVÉ TÁBORY') || menuLabel === 'POBYTOVÉ TÁBORY') {
                    ev.preventDefault();
                    ev.stopPropagation();
                    ev.stopImmediatePropagation();
                    console.log('Normal dropdown: Redirecting to /pobytove-tabory');
                    window.location.assign('/pobytove-tabory');
                }
            }
        }, true);
    }
});