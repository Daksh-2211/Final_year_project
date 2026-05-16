FROM odoo:18.0

LABEL maintainer="CodeTrade India Pvt. Ltd."

USER root

RUN apt-get update && apt-get install -y git nano

ADD ./entrypoint.sh /entrypoint.sh
ADD ./odoo.conf /etc/odoo/odoo.conf
ADD ./wait-for-psql.py /usr/local/bin/wait-for-psql.py

RUN chmod +x /entrypoint.sh && \
    chmod +x /usr/local/bin/wait-for-psql.py && \
    mkdir -p /mnt/extra-addons /var/lib/odoo/sessions /var/lib/odoo/filestore && \
    chown -R odoo:odoo /mnt/extra-addons /var/lib/odoo

COPY ./custom_req.txt /tmp/custom_req.txt

RUN pip3 install -r /tmp/custom_req.txt --break-system-packages

VOLUME ["/var/lib/odoo", "/mnt/extra-addons"]

EXPOSE 8069 8071 8072

ENV ODOO_RC=/etc/odoo/odoo.conf

USER odoo

ENTRYPOINT ["/entrypoint.sh"]

CMD ["odoo"]
