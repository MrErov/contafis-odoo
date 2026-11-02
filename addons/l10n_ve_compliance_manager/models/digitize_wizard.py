import base64
import json
import logging
import time

import requests
from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError

from .digitize_client import DIGITIZE_ALLOWED_EXTENSIONS, _get_session_id, post_digitize

_logger = logging.getLogger(__name__)


class DigitizeWizard(models.TransientModel):
    _name = 'l10n.ve.digitize.wizard'
    _description = 'Wizard de digitalización de facturas'

    type = fields.Selection(
        [
            ('purchase', 'Compra'),
            ('sale', 'Venta'),
        ],
        string='Tipo de Operación',
        required=True,
        default='purchase',
    )
    document_type_hint = fields.Selection(
        [
            ('auto', 'Automático'),
            ('factura_z', 'Factura'),
            ('nota_credito', 'Nota de Crédito'),
            ('nota_debito', 'Nota de Débito'),
        ],
        string='Tipo de Documento',
        required=True,
        default='auto',
        help="Tipo de documento esperado. 'Automático' deja que el servicio lo detecte.",
    )
    image = fields.Binary(string='Imagen de la factura', attachment=True)
    filename = fields.Char(string='Nombre del archivo')
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('done', 'Analizado'),
            ('error', 'Error'),
        ],
        string='Estado',
        default='draft',
        readonly=True,
    )
    confidence = fields.Float(string='Confianza', readonly=True, digits=(3, 2))
    detected_document_type = fields.Char(string='Tipo de Documento Detectado', readonly=True)
    error_message = fields.Char(string='Mensaje de Error', readonly=True)

    # Vista previa de los datos extraídos (RF-06/RF-10). Solo lectura: el
    # contador los revisa antes de pasarlos al wizard de factura física.
    supplier_name = fields.Char(string='Razón Social Extraída', readonly=True)
    supplier_rif = fields.Char(string='RIF Extraído', readonly=True)
    invoice_number = fields.Char(string='N° Factura Extraído', readonly=True)
    control_number = fields.Char(string='N° Control Extraído', readonly=True)
    invoice_date = fields.Date(string='Fecha de Emisión Extraída', readonly=True)
    due_date = fields.Date(string='Fecha de Vencimiento Extraída', readonly=True)
    currency_code = fields.Char(string='Moneda Extraída', readonly=True)
    subtotal = fields.Float(string='Subtotal Extraído', readonly=True)
    iva_rate = fields.Float(string='Tasa IVA Extraída', readonly=True)
    iva_amount = fields.Float(string='IVA Extraído', readonly=True)
    igtf_amount = fields.Float(string='IGTF Extraído', readonly=True)
    total = fields.Float(string='Total Extraído', readonly=True)
    credit_note_ref = fields.Char(string='Referencia Nota de Crédito', readonly=True)
    debit_note_ref = fields.Char(string='Referencia Nota de Débito', readonly=True)
    extracted_json = fields.Text(string='Datos Extraídos (JSON)', readonly=True)
    warnings_json = fields.Text(string='Advertencias (JSON)', readonly=True)

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def _get_param(self, key, default=''):
        """Read an ``ir.config_parameter`` value.

        ``sudo()`` is justified: these are technical settings, not business
        data, and the end user must not need ACL access on the parameter model
        (same pattern already used by ``discuss_channel.py``).
        """
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    def _get_timeout(self):
        try:
            return max(float(self._get_param('l10n_ve_digitize.timeout_seconds', '30') or 30), 1.0)
        except (TypeError, ValueError):
            return 30.0

    def _get_max_image_mb(self):
        try:
            return float(self._get_param('l10n_ve_digitize.max_image_mb', '5') or 5)
        except (TypeError, ValueError):
            return 5.0

    def _get_url(self):
        return (self._get_param('l10n_ve_digitize.url') or '').strip()

    # ------------------------------------------------------------------
    # Input validation
    # ------------------------------------------------------------------
    def _get_extension(self):
        filename = (self.filename or '').strip()
        if '.' not in filename:
            return ''
        return '.' + filename.rsplit('.', 1)[-1].lower()

    def _get_image_base64(self):
        """Normalize the Binary value to a plain base64 string (no ``data:`` prefix)."""
        image = self.image
        if isinstance(image, bytes):
            try:
                image = image.decode('ascii')
            except UnicodeDecodeError:
                # Raw binary payload: encode it instead of dropping it.
                return base64.b64encode(image).decode('ascii')
        image = (image or '').strip()
        if image.startswith('data:'):
            image = image.split(',', 1)[-1]
        return image

    def _get_image_size_mb(self):
        image = self.image
        if not image:
            return 0.0
        if isinstance(image, str):
            image = image.encode('ascii', 'ignore')
        try:
            raw = base64.b64decode(image, validate=False)
        except (ValueError, TypeError):
            raw = image
        return len(raw) / (1024 * 1024)

    def _validate_image(self):
        if not self.image:
            raise ValidationError(_("Adjunte una imagen de la factura antes de analizar."))
        extension = self._get_extension()
        if extension not in DIGITIZE_ALLOWED_EXTENSIONS:
            raise ValidationError(
                _("Formato no soportado. Se aceptan imágenes JPG, JPEG, PNG o WEBP.")
            )
        size_mb = self._get_image_size_mb()
        max_mb = self._get_max_image_mb()
        if size_mb > max_mb:
            raise ValidationError(
                _(
                    "La imagen pesa %.1f MB y supera el límite de %.1f MB. "
                    "Reduzca su tamaño antes de analizar."
                )
                % (size_mb, max_mb)
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _reload_action(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Digitalizar Factura'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _set_error(self, message):
        self.write({'state': 'error', 'error_message': message})
        return self._reload_action()

    def action_digitize(self):
        """Validate the input, call ``/digitize`` and map the outcome.

        The wizard never creates an ``account.move``. Service failures are
        reported through ``state='error'`` and ``error_message`` (RF-12); only
        invalid input (extension/size) raises ``ValidationError``.
        """
        self.ensure_one()
        self._validate_image()

        url = self._get_url()
        if not url:
            return self._set_error(
                _(
                    "La digitalización no está configurada. "
                    "Configure la URL en Ajustes → ContaFis AI."
                )
            )

        session_id = _get_session_id()
        if not session_id:
            return self._set_error(
                _("🔐 Sesión no detectada. Recargá Odoo e intentá de nuevo.")
            )

        payload = {
            'image_base64': self._get_image_base64(),
            'filename': self.filename,
            'document_type': self.document_type_hint or 'auto',
        }
        size_mb = self._get_image_size_mb()
        timeout = self._get_timeout()

        start_time = time.time()
        try:
            response = post_digitize(url, session_id, payload, timeout=timeout)
        except requests.Timeout:
            _logger.warning(
                "Digitize request for %s timed out after %.2fs",
                self.filename,
                time.time() - start_time,
            )
            return self._set_error(
                _("⏱️ El servicio de digitalización tardó demasiado. Reintentá en unos minutos.")
            )
        except requests.RequestException as error:
            _logger.error(
                "Digitize request for %s failed after %.2fs: %s",
                self.filename,
                time.time() - start_time,
                error,
            )
            return self._set_error(
                _(
                    "❌ No se pudo conectar con el servicio de digitalización. "
                    "Verifique la URL configurada."
                )
            )

        elapsed = time.time() - start_time
        status = response.status_code
        # Only metadata is logged: never the base64 image nor the session id.
        _logger.info(
            "Digitize request for %s (%.2f MB) -> HTTP %s in %.2fs",
            self.filename,
            size_mb,
            status,
            elapsed,
        )

        if status in (401, 403):
            return self._set_error(
                _("🔐 Tu sesión de Odoo expiró o no es válida. Recargá Odoo e intentá de nuevo.")
            )
        if status == 503:
            return self._set_error(
                _("🔄 El servicio de digitalización no está disponible ahora. Reintentá en unos minutos.")
            )
        if status >= 500:
            return self._set_error(
                _("🔧 Error del servidor de digitalización. Reintentá en unos minutos.")
            )
        if status >= 400:
            return self._set_error(
                _(
                    "La imagen o el formato fue rechazado por el servicio. "
                    "Verifique extensión y tamaño."
                )
            )

        try:
            data = response.json()
        except ValueError:
            return self._set_error(
                _("⚠️ El servicio devolvió una respuesta que no es JSON.")
            )

        parsed = self._parse_response(data)
        if parsed is None:
            return self._set_error(
                _(
                    "⚠️ La respuesta del servicio está incompleta. "
                    "Reintentá o cargue la factura a mano."
                )
            )

        extracted = parsed['extracted']
        merged_warnings = self._merge_warnings(
            parsed['warnings'], self._build_local_warnings(extracted)
        )
        values = {
            'state': 'done',
            'error_message': False,
            'confidence': parsed['confidence'],
            'detected_document_type': parsed['document_type'],
            'extracted_json': json.dumps(extracted, ensure_ascii=False, default=str),
            'warnings_json': json.dumps(
                merged_warnings, ensure_ascii=False, default=str
            ),
        }
        values.update(self._get_preview_values(extracted))
        self.write(values)
        return self._reload_action()

    # ------------------------------------------------------------------
    # Response parsing and mapping
    # ------------------------------------------------------------------
    def _parse_response(self, data):
        """Normalize the service payload (RF-06, tolerant parsing).

        Returns ``None`` when the payload is unusable, so callers keep the
        single "incomplete response" message. Never raises on malformed data.
        """
        if (
            not isinstance(data, dict)
            or not data.get('document_type')
            or 'confidence' not in data
            or not isinstance(data.get('extracted'), dict)
        ):
            return None

        try:
            confidence = float(data.get('confidence'))
        except (TypeError, ValueError):
            return None

        warnings = data.get('warnings')
        if not isinstance(warnings, list):
            warnings = []

        return {
            'document_type': str(data['document_type']),
            'confidence': min(max(confidence, 0.0), 1.0),
            'extracted': data['extracted'],
            'warnings': warnings,
        }

    def _coerce_float(self, value):
        """Return ``value`` as float, or ``None`` when it is not numeric."""
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_date(self, value):
        """Return ``value`` as date, or ``None`` when it cannot be parsed."""
        if not value:
            return None
        try:
            return fields.Date.to_date(value)
        except (TypeError, ValueError):
            return None

    def _get_preview_values(self, extracted):
        """Read-only preview values written right after a successful analysis."""
        extracted = extracted if isinstance(extracted, dict) else {}
        return {
            'supplier_name': extracted.get('supplier_name') or False,
            'supplier_rif': extracted.get('supplier_rif') or False,
            'invoice_number': extracted.get('invoice_number') or False,
            'control_number': extracted.get('control_number') or False,
            'invoice_date': self._coerce_date(extracted.get('invoice_date')),
            'due_date': self._coerce_date(extracted.get('due_date')),
            'currency_code': extracted.get('currency') or False,
            'subtotal': self._coerce_float(extracted.get('subtotal')) or 0.0,
            'iva_rate': self._coerce_float(extracted.get('iva_rate')) or 0.0,
            'iva_amount': self._coerce_float(extracted.get('iva_amount')) or 0.0,
            'igtf_amount': self._coerce_float(extracted.get('igtf_amount')) or 0.0,
            'total': self._coerce_float(extracted.get('total')) or 0.0,
            'credit_note_ref': extracted.get('credit_note_ref') or False,
            'debit_note_ref': extracted.get('debit_note_ref') or False,
        }

    def _get_base_field_for_rate(self, rate):
        """Map an IVA rate to the physical wizard base field (RF-10)."""
        if abs(rate - 0.16) < 1e-6:
            return 'default_base_general'
        if abs(rate - 0.08) < 1e-6:
            return 'default_base_reduced'
        if rate > 1.0:
            return None
        if rate > 0.16:
            return 'default_base_additional'
        if abs(rate) < 1e-6:
            return 'default_base_not_taxed'
        return None

    def _map_extracted_to_invoice_defaults(self, extracted):
        """Build the ``default_*`` context for the physical invoice wizard.

        Pure with respect to writes: no ``create``/``write`` and no ``sudo``.
        ``self.env`` is only used to resolve the currency and an existing
        partner (RF-10/RF-17).
        """
        extracted = extracted if isinstance(extracted, dict) else {}
        defaults = {'default_type': self.type}

        rif = extracted.get('supplier_rif')
        if rif:
            defaults['default_partner_vat'] = rif

        supplier_name = extracted.get('supplier_name')
        if supplier_name:
            defaults['default_new_partner_name'] = supplier_name

        for source, target in (
            ('invoice_number', 'default_invoice_number'),
            ('control_number', 'default_control_number'),
        ):
            value = extracted.get(source)
            if value:
                defaults[target] = value

        for source, target in (
            ('invoice_date', 'default_invoice_date'),
            ('due_date', 'default_invoice_date_due'),
        ):
            # Emit False explicitly: `invoice_date` has a `today` default in the
            # destination wizard, so omitting the key would invent a fiscal date.
            defaults[target] = self._coerce_date(extracted.get(source)) or False

        currency_code = str(extracted.get('currency') or '').strip().upper()
        if currency_code == 'VES':
            defaults['default_currency_id'] = self.env.company.currency_id.id
        elif currency_code == 'USD':
            usd = self.env['res.currency'].search(
                [('name', '=', 'USD'), ('active', 'in', [True, False])], limit=1
            )
            defaults['default_currency_id'] = (
                usd.id if usd else self.env.company.currency_id.id
            )

        subtotal = self._coerce_float(extracted.get('subtotal'))
        iva_rate = self._coerce_float(extracted.get('iva_rate'))
        if subtotal is not None and subtotal != 0 and iva_rate is not None:
            base_field = self._get_base_field_for_rate(iva_rate)
            if base_field:
                defaults[base_field] = subtotal

        total = self._coerce_float(extracted.get('total'))
        if total is not None:
            defaults['default_physical_total'] = total

        lines = extracted.get('lines')
        if isinstance(lines, list):
            descriptions = []
            for line in lines:
                if not isinstance(line, dict):
                    continue
                description = str(line.get('description') or '').strip()
                if description:
                    descriptions.append(description)
            if descriptions:
                defaults['default_concept'] = ' / '.join(descriptions)[:255]

        if rif:
            rif_clean = self.env['l10n.ve.physical.invoice.wizard']._clean_rif(rif)
            if self.env['l10n.ve.import.wizard']._validate_rif(rif):
                partner = self.env['res.partner'].search(
                    [
                        '|',
                        ('vat', '=', rif),
                        ('vat', '=', rif_clean),
                        ('company_id', 'in', [False, self.env.company.id]),
                    ],
                    limit=1,
                )
                if partner:
                    defaults['default_partner_id'] = partner.id
                    if 'default_new_partner_name' not in defaults:
                        defaults['default_new_partner_name'] = partner.name

        return defaults

    def _build_local_warnings(self, extracted):
        """Local warnings for data the service returned incomplete/invalid.

        Only the backend contract codes are allowed (RF-11/RF-12). Results are
        deduplicated by ``(code, field)``.
        """
        extracted = extracted if isinstance(extracted, dict) else {}
        warnings = []

        def add(code, field, message, value=None):
            warnings.append(
                {
                    'code': code,
                    'message': message,
                    'field': field,
                    'extracted_value': value,
                }
            )

        required = (
            ('supplier_rif', 'RIF del proveedor'),
            ('supplier_name', 'nombre o razón social del proveedor'),
            ('invoice_number', 'número de factura'),
            ('control_number', 'número de control'),
        )
        for field, label in required:
            if not extracted.get(field):
                add(
                    'missing_field',
                    field,
                    _("Falta el %s en la respuesta del servicio.") % label,
                )

        # `invoice_date` is required in the destination wizard: warn when it is
        # absent. `invoice_date_due` is optional: only warn on a bad format.
        value = extracted.get('invoice_date')
        if not value:
            add(
                'missing_field',
                'invoice_date',
                _("Falta la fecha de emisión en la respuesta del servicio."),
            )
        elif self._coerce_date(value) is None:
            add(
                'parsing_error',
                'invoice_date',
                _("La fecha de emisión no tiene un formato válido (AAAA-MM-DD)."),
                value,
            )

        value = extracted.get('due_date')
        if value and self._coerce_date(value) is None:
            add(
                'parsing_error',
                'due_date',
                _("La fecha de vencimiento no tiene un formato válido (AAAA-MM-DD)."),
                value,
            )

        subtotal = extracted.get('subtotal')
        if subtotal is None:
            add(
                'missing_field',
                'subtotal',
                _("Falta el subtotal en la respuesta del servicio."),
            )
        elif self._coerce_float(subtotal) is None:
            add(
                'parsing_error',
                'subtotal',
                _("El subtotal extraído no es un número válido."),
                subtotal,
            )

        iva_rate = extracted.get('iva_rate')
        if iva_rate is None:
            add(
                'missing_field',
                'iva_rate',
                _("Falta la tasa de IVA en la respuesta del servicio."),
            )
        else:
            rate = self._coerce_float(iva_rate)
            if rate is None:
                add(
                    'parsing_error',
                    'iva_rate',
                    _("La tasa de IVA extraída no es un número válido."),
                    iva_rate,
                )
            elif rate < 0:
                add(
                    'parsing_error',
                    'iva_rate',
                    _("La tasa de IVA extraída no puede ser negativa."),
                    iva_rate,
                )
            elif 0 < rate < 0.16 and abs(rate - 0.08) >= 1e-6:
                add(
                    'parsing_error',
                    'iva_rate',
                    _(
                        "La tasa de IVA extraída no corresponde a 16 %, 8 % "
                        "ni 0 %; revise las bases manualmente."
                    ),
                    iva_rate,
                )
            elif rate > 1.0:
                add(
                    'parsing_error',
                    'iva_rate',
                    _("La tasa de IVA extraída supera el 100 %; verifique el dato."),
                    iva_rate,
                )

        rif = extracted.get('supplier_rif')
        if rif and not self.env['l10n.ve.import.wizard']._validate_rif(rif):
            add(
                'invalid_rif',
                'supplier_rif',
                _("El RIF extraído no es válido (dígito de control incorrecto)."),
                rif,
            )

        seen = set()
        unique = []
        for warning in warnings:
            key = (warning['code'], warning['field'])
            if key in seen:
                continue
            seen.add(key)
            unique.append(warning)
        return unique

    def _merge_warnings(self, service_warnings, local_warnings):
        """Concat service + local warnings, deduplicated by ``(code, field)``.

        The service warning wins on collision: the backend already reports
        ``missing_field``/``invalid_rif`` and its message is authoritative.
        """
        merged = []
        seen = set()
        for source in (service_warnings or [], local_warnings or []):
            if not isinstance(source, list):
                continue
            for warning in source:
                if not isinstance(warning, dict):
                    continue
                key = (warning.get('code'), warning.get('field'))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(warning)
        return merged

    def action_apply_to_invoice(self):
        """Open the physical invoice wizard pre-filled with the extracted data."""
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("Analice la imagen antes de usar los datos."))

        try:
            extracted = json.loads(self.extracted_json or '{}')
        except (TypeError, ValueError):
            extracted = {}

        defaults = self._map_extracted_to_invoice_defaults(extracted)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura Física Rápida'),
            'res_model': 'l10n.ve.physical.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': defaults,
        }
