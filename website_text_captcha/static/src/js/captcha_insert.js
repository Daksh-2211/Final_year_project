/** @odoo-module **/

odoo.define('website_text_captcha.captcha_insert', [], function (require) {
    'use strict';

    const CAPTCHA_HTML = `
<div class="col-12 s_website_form_field mb-3 field-captcha" data-type="char" data-name="captcha_input">
    <div class="row s_col_no_resize">
        <label class="col-form-label col-sm-auto s_website_form_label" style="width: 200px" for="captcha_input">
            <span class="s_website_form_label_content">Security Check</span>
            <span class="s_website_form_mark"> *</span>
        </label>
        <div class="col-sm">
            <div class="d-flex align-items-center gap-2">
                <img data-src="/captcha/image"
                     alt="Captcha"
                     class="img-fluid border rounded"
                     onclick="this.src = this.dataset.src + '?' + new Date().getTime();"
                     style="cursor: pointer; height: 50px; min-width: 140px;"
                     title="Click to Refresh"/>
                <input type="text"
                       class="form-control s_website_form_input"
                       name="captcha_input"
                       required="required"
                       placeholder="ENTER CODE"
                       style="width: 140px; text-transform: uppercase; font-weight: bold;"/>
                <small class="text-muted d-none d-md-block ms-2">
                    <i class="fa fa-refresh"></i> Click image to refresh
                </small>
            </div>
        </div>
    </div>
</div>`;

    function insertCaptcha() {
        console.log("[Captcha] Attempting insertion check");

        const submitDiv = document.querySelector(
            '.s_website_form_submit:not([data-captcha-inserted]), ' +
            '.s_website_form .s_website_form_send:not([data-captcha-inserted]), ' +
            '.s_website_form .btn-primary.s_website_form_send:not([data-captcha-inserted])'
        );

        if (!submitDiv) {
            console.log("[Captcha] No submit div found - skipping");
            return;
        }

        if (document.querySelector('.field-captcha')) {
            console.log("[Captcha] Already inserted - skipping");
            return;
        }

        submitDiv.dataset.captchaInserted = 'true';

        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = CAPTCHA_HTML.trim();
        const captchaElement = tempDiv.firstElementChild;

        submitDiv.parentNode.insertBefore(captchaElement, submitDiv);

        // Load image explicitly once
        const captchaImg = captchaElement.querySelector('img');
        if (captchaImg) {
            captchaImg.src = captchaImg.dataset.src + '?' + new Date().getTime();
            console.log("[Captcha] Loaded image explicitly");
        }

        console.log("[Captcha] Inserted before submit button");
    }

    // Run once after page fully loaded
    window.addEventListener('load', insertCaptcha);

    // Watch for dynamic insertions
    const observer = new MutationObserver(insertCaptcha);
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});
