/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */



$(document).ready(function() {
    if (localStorage.getItem('webkul2019promotionbar')) {
        var div_ids = localStorage.getItem('webkul2019promotionbar').split(',');
        for(var index=1; index<div_ids.length; index++) {
            var div_selector = "div[data-id='" + div_ids[index] + "']";
        }
    }
    else {
        var list = [];
        localStorage.setItem('webkul2019promotionbar', list);
    }
    $('.close_promotion').on('click', function() {
        $(this).closest('.promotion').remove();
        var temp = [localStorage.getItem('webkul2019promotionbar')];
        temp.push($(this).closest('.promotion').data('id'));
        localStorage.setItem('webkul2019promotionbar', temp);
    });
    $('.promotion, .promotion_link').on('click', function(event) {
        event.stopPropagation();
        if ($(this).attr('class') == 'promotion_link') {
            var temp = $(this).attr('data-target');
        }
        else {
            var temp = $(this).find('.promotion_link').attr('data-target');
        }
        $(temp).modal("show");
    });
});

