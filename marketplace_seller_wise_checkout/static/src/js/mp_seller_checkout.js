/** @odoo-module **/

/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : https://store.webkul.com/license.html/ */

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";
import "@website_sale/js/website_sale";

$(document).on('click', '#add_to_cart', function(ev) {
  $('#my_cart').removeClass('d-none')

})

    $(document).on('click', 'a[href*="/shop/checkout"]', function(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var seller = '';
        var seller_id = '';
        var href = $(this).attr('href')
        var index = href.indexOf('seller=')-1
        var index_express = href.indexOf('express=')-1
        if (index > 0){
            seller = href.substring(index) // this gives ?seller=51
        }
        seller_id = seller.slice(seller.indexOf('=') + 1).split('&')[0]; 

        if (seller != seller_id){
            seller_id= parseInt(seller_id)
        }
        rpc('/seller/wise/checkout',  {
            'seller_id': seller_id,
        }).then(function(res) {
            if (index_express > 0){
                window.location.href = '/shop/checkout?express=1';
            }
            else{
                window.location.href = '/shop/checkout';
            }
        });
    });

    publicWidget.registry.WebsiteSale.include({
    // sAnimations.registry.WebsiteSale.include({
        /**
         * @override
         * @private
         */
        _changeCartQuantity: function ($input, value, $dom_optional, line_id, productIDs) {
            $($dom_optional).toArray().forEach((elem) => {
                $(elem).find('.js_quantity').text(value);
                productIDs.push($(elem).find('span[data-product-id]').data('product-id'));
            });
            $input.data('update_change', true);
            rpc(
                "/shop/cart/update_json",
                {
                    line_id: line_id,
                    product_id: parseInt($input.data('product-id'), 10),
                    set_qty: value,
                    display: true,

            }).then(function (data) {

                var $closest_order = $input.closest('#cart_products');
                var js_cart_summary_id = $closest_order.parent().attr("id")
                var total_cart_id = ''
                if (js_cart_summary_id === 'admin_cart'){
                  total_cart_id = 'admin_cart_checkout'
                }
                else{
                  var total_cart_id_split = js_cart_summary_id.split('_')

                  if (total_cart_id_split.length >1 ){
                    total_cart_id = '_'+total_cart_id_split[1]
                  }
                }

                var js_cart_summary = $('#'+total_cart_id).find("div[id='cart_total']")
                $closest_order.next('.js_cart_lines').first().remove() //to make previous total price row blank
                $closest_order.next('.js_cart_lines').first().remove()
                $closest_order.next('.js_cart_lines').first().remove()
                if (data.no_line){
                    $input.closest('.js_cart_lines').parent().next().remove();
                    $input.closest('.js_cart_lines').parent().remove();
                    window.location = '/shop/cart';
                }
                $input.data('update_change', false);
                var check_value = parseInt($input.val() || 0, 10);
                if (isNaN(check_value)) {
                    check_value = 1;
                }
                if (value !== check_value) {
                    $input.trigger('change');
                    return;
                }
                var $q = $(".my_cart_quantity");
                if (data.total_cart_qty) {
                    $q.parents('li:first').removeClass("hidden");
                }
                else {
                    window.location = '/shop/cart';
                }
                $q.html(data.total_cart_qty).hide().fadeIn(600);                
                $input.val(data.quantity);
                $('.js_quantity[data-line-id='+line_id+']').val(data.quantity).html(data.quantity);
                $closest_order.prev('.js_cart_lines').remove();
                $closest_order.prev('.js_cart_lines').remove();
                js_cart_summary.replaceWith(data['website_sale.total']);
                $closest_order.replaceWith(data['website_sale.cart_lines'])
                if (data.warning) {
                    var cart_alert = $('.oe_cart').parent().find('#data_warning');
                    if (cart_alert.length === 0) {
                        $('.oe_cart').prepend('<div class="alert alert-danger alert-dismissable" role="alert" id="data_warning">'+
                            '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">&times;</button> ' + data.warning + '</div>');
                    }
                    else {
                        cart_alert.html('<button type="button" class="close" data-dismiss="alert" aria-hidden="true">&times;</button> ' + data.warning);
                    }
                    $input.val(data.quantity);
                }
            });
        },
    })

