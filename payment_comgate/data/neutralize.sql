-- disable comgate payment provider
UPDATE payment_provider
   SET comgate_key_id = NULL,
       comgate_key_secret = NULL;