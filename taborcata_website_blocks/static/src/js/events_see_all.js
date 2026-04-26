/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.TaborcataSeeAllRedirect = publicWidget.Widget.extend({
    selector: '#wrapwrap',

    start() {
        this._super.apply(this, arguments);

        document.addEventListener('click', (ev) => {
            let seeAllBtn = ev.target.closest('a[href="/event"], .s_dynamic_snippet_main_page_url');
            
            if (seeAllBtn) {
                const path = window.location.pathname;
                let newHref = null;

                if (path.includes('petrzalka')) newHref = '/events/denny/petrzalka';
                else if (path.includes('ruzinov') || path.includes('laserarena')) newHref = '/events/denny/ruzinov';
                else if (path.includes('lamac') || path.includes('spacepark')) newHref = '/events/denny/lamac';
                else if (path.includes('raca')) newHref = '/events/denny/raca';
                else if (path.includes('karlova-ves')) newHref = '/events/denny/karlova-ves';
                else if (path.includes('pobytove') || path.includes('pobytovy') || path.includes('kemp') || path.includes('stanovy') || path.includes('carodejnicka') || path.includes('clenstvo')) newHref = '/events/pobytove';
                else if (path.includes('denne') || path.includes('denny')) newHref = '/events/denny';

                if (newHref) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    window.location.assign(newHref);
                }
            }
        }, true);
    }
});
