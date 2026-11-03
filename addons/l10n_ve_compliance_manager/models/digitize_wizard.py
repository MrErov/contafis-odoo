import base64
import html
import json
import logging
import time

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .digitize_client import DIGITIZE_ALLOWED_EXTENSIONS, _get_session_id, post_digitize

_logger = logging.getLogger(__name__)


class DigitizeWizard(models.TransientModel):
    _name = 'l10n.ve.digitize.wizard'
    _description = 'Wizard de digitalizaci\xf3n de facturas'

    type = fields.Selection(
        [
            ('purchase', 'Compra'),
            ('sale', 'Venta'),
        ],
        string='Tipo de Operaci\xf3n',
        required=True,
        default='purchase',
    )
    document_type_hint = fields.Selection(
        [
            ('auto', 'Autom\xe1tico'),
            ('factura_z', 'Factura'),
            ('nota_credito', 'Nota de Cr\xe9dito'),
            ('nota_debito', 'Nota de D\xe9bito'),
        ],
        string='Tipo de Documento',
        required=True,
        default='auto',
        help="Tipo de documento esperado. 'Autom\xe1tico' deja que el servicio lo detecte.",
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

    # Vista previa de los datos extra\xeddos (RF-06/RF-10). Solo lectura: el
    # contador los revisa antes de pasarlos al wizard de factura f\xedsica.
    supplier_name = fields.Char(string='Raz\xf3n Social Extra\xedda', readonly=True)
    supplier_rif = fields.Char(string='RIF Extra\xeddo', readonly=True)
    invoice_number = fields.Char(string='N\xb0 Factura Extra\xeddo', readonly=True)
    control_number = fields.Char(string='N\xb0 Control Extra\xeddo', readonly=True)
    invoice_date = fields.Date(string='Fecha de Emisi\xf3n Extra\xedda', readonly=True)
    due_date = fields.Date(string='Fecha de Vencimiento Extra\xedda', readonly=True)
    currency_code = fields.Char(string='Moneda Extra\xedda', readonly=True)
    subtotal = fields.Float(string='Subtotal Extra\xeddo', readonly=True)
    iva_rate = fields.Float(string='Tasa IVA Extra\xedda', readonly=True)
    iva_amount = fields.Float(string='IVA Extra\xeddo', readonly=True)
    igtf_amount = fields.Float(string='IGTF Extra\xeddo', readonly=True)
    total = fields.Float(string='Total Extra\xeddo', readonly=True)
    credit_note_ref = fields.Char(string='Referencia Nota de Cr\xe9dito', readonly=True)
    debit_note_ref = fields.Char(string='Referencia Nota de D\xe9bito', readonly=True)
    extracted_json = fields.Text(string='Datos Extra\xeddos (JSON)', readonly=True)
    warnings_json = fields.Text(string='Advertencias (JSON)', readonly=True)

    # L\xedneas extra\xeddas (T3 - RF-08)
    digitize_line_ids = fields.One2many(
        'l10n.ve.digitize.line',
        'wizard_id',
        string='L\xedneas Extra\xeddas',
        readonly=True,
    )

    # UI de confianza y advertencias (T3 - RF-07, RF-08)
    confidence_pct = fields.Integer(
        string='Confianza (%)', compute='_compute_confidence_pct', readonly=True,
    )
    has_warnings = fields.Boolean(
        string='Tiene Advertencias', compute='_compute_has_warnings', readonly=True,
    )
    warnings_text = fields.Text(
        string='Advertencias', compute='_compute_warnings_text', readonly=True,
    )
    total_mismatch = fields.Boolean(
        string='Descuadre de Total', compute='_compute_total_mismatch', readonly=True,
    )

    # ------------------------------------------------------------------
    # Compute methods (T3 - RF-07, RF-08)
    # ------------------------------------------------------------------
    @api.depends('confidence')
    def _compute_confidence_pct(self):
        """Convert confidence (0.0\u20131.0) to percentage (0\u2013100)."""
        for wizard in self:
            wizard.confidence_pct = int(round(wizard.confidence * 100)) if wizard.confidence else 0

    @api.depends('warnings_json')
    def _compute_has_warnings(self):
        """True when there is at least one warning."""
        for wizard in self:
            try:
                wizard.has_warnings = bool(json.loads(wizard.warnings_json or '[]'))
            except (TypeError, ValueError):
                wizard.has_warnings = False

    @api.depends('warnings_json')
    def _compute_warnings_text(self):
        """Build plain-text warnings from warnings_json.

        Format: "code: message\n" per warning. Never markup/HTML.
        HTML entities in messages are escaped to prevent XSS.
        """
        for wizard in self:
            text = ''
            if wizard.warnings_json:
                try:
                    warnings = json.loads(wizard.warnings_json)
                except (TypeError, ValueError):
                    warnings = []
                if isinstance(warnings, list):
                    lines = []
                    for w in warnings:
                        if not isinstance(w, dict):
                            continue
                        code = w.get('code') or ''
                        message = w.get('message') or ''
                        # Escape HTML entities to ensure plain text output
                        message = html.escape(message)
                        if code or message:
                            lines.append(f'{code}: {message}')
                    text = '\n'.join(lines) if lines else ''
            wizard.warnings_text = text

    @api.depends('total', 'subtotal', 'iva_amount', 'iva_rate', 'igtf_amount')
    def _compute_total_mismatch(self):
        """True when extracted total differs from subtotal + iva_amount (tolerance 0.01).

        IGTF is excluded from the calculation (informational only).
        If the difference equals IGTF amount (within tolerance), it's not a mismatch.
        If iva_amount is missing but iva_rate is known, recalculate.
        """
        for wizard in self:
            mismatch = False
            total = wizard.total or 0.0
            subtotal = wizard.subtotal or 0.0
            iva_amount = wizard.iva_amount          # None if not provided by service
            igtf_amount = wizard.igtf_amount or 0.0

            # Recalculate iva_amount only if NOT provided by service
            if iva_amount is None and subtotal:
                rate = wizard.iva_rate or 0.0
                if abs(rate - 0.16) < 1e-6 or abs(rate - 0.08) < 1e-6:
                    iva_amount = subtotal * rate
                elif abs(rate) < 1e-6:
                    iva_amount = 0.0
                else:
                    iva_amount = 0.0  # unknown rate -> cannot validate

            if total and subtotal and iva_amount is not None:
                calculated = subtotal + iva_amount
                diff = abs(total - calculated)
                if diff > 0.01:
                    # If the difference equals IGTF amount (within tolerance), it's not a mismatch
                    if abs(diff - igtf_amount) > 0.01:
                        mismatch = True
            wizard.total_mismatch = mismatch

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
                _("Formato no soportado. Se aceptan im\xe1genes JPG, JPEG, PNG o WEBP.")
            )
        size_mb = self._get_image_size_mb()
        max_mb = self._get_max_image_mb()
        if size_mb > max_mb:
            raise ValidationError(
                _(
                    "La imagen pesa %.1f MB y supera el l\xedmite de %.1f MB. "
                    "Reduzca su tama\xf1o antes de analizar."
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
                    "La digitalizaci\xf3n no est\xe1 configurada. "
                    "Configure la URL en Ajustes \u2192 ContaFis AI."
                )
            )

        session_id = _get_session_id()
        if not session_id:
            return self._set_error(
                _("\U0001f510 Sesión no detectada. Recarg\xe1 Odoo e intent\xe1 de nuevo.")
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
                _("\u23f1\ufe0f El servicio de digitalizaci\xf3n tard\xe3 demasiado. Reintent\xe1 en unos minutos.")
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
                    "\u274c No se pudo conectar con el servicio de digitalizaci\xf3n. "
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
                _("\U0001f510 Tu sesi\xf3n de Odoo expir\xf3 o no es v\xe1lida. Recarg\xe1 Odoo e intent\xe1 de nuevo.")
            )
        if status == 503:
            return self._set_error(
                _("\U0001f504 El servicio de digitalizaci\xf3n no est\xe1 disponible ahora. Reintent\xe1 en unos minutos.")
            )
        if status >= 500:
            return self._set_error(
                _("\U0001f527 Error del servidor de digitalizaci\xf3n. Reintent\xe1 en unos minutos.")
            )
        if status >= 400:
            return self._set_error(
                _(
                    "La imagen o el formato fue rechazado por el servicio. "
                    "Verifique extensi\xf3n y tama\xf1o."
                )
            )

        try:
            data = response.json()
        except ValueError:
            return self._set_error(
                _("\u26a0\ufe0f El servicio devolvi\xf3 una respuesta que no es JSON.")
            )

        parsed = self._parse_response(data)
        if parsed is None:
            return self._set_error(
                _(
                    "\u26a0\ufe0f La respuesta del servicio est\xe1 incompleta. "
                    "Reintent\xe1 o cargue la factura a mano."
                )
            )

        extracted = parsed['extracted']
        merged_warnings = self._merge_warnings(
            parsed['warnings'], self._build_local_warnings(extracted)
        )
        # Recreate extracted lines (T3 - RF-08)
        lines_vals = []
        for line in extracted.get('lines') or []:
            if isinstance(line, dict):
                lines_vals.append((0, 0, {
                    'description': line.get('description') or '',
                    'quantity': float(line.get('quantity') or 0.0),
                    'unit_price': float(line.get('unit_price') or 0.0),
                    'total': float(line.get('total') or 0.0),
                }))
        values = {
            'state': 'done',
            'error_message': False,
            'confidence': parsed['confidence'],
            'detected_document_type': parsed['document_type'],
            'extracted_json': json.dumps(extracted, ensure_ascii=False, default=str),
            'warnings_json': json.dumps(
                merged_warnings, ensure_ascii=False, default=str
            ),
            'digitize_line_ids': lines_vals,
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
            ('supplier_name', 'nombre o raz\xf3n social del proveedor'),
            ('invoice_number', 'n\xfamero de factura'),
            ('control_number', 'n\xfamero de control'),
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
                _("Falta la fecha de emisi\xf3n en la respuesta del servicio."),
            )
        elif self._coerce_date(value) is None:
            add(
                'parsing_error',
                'invoice_date',
                _("La fecha de emisi\xf3n no tiene un formato v\xe1lido (AAAA-MM-DD)."),
                value,
            )

        value = extracted.get('due_date')
        if value and self._coerce_date(value) is None:
            add(
                'parsing_error',
                'due_date',
                _("La fecha de vencimiento no tiene un formato v\xe1lido (AAAA-MM-DD)."),
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
                _("El subtotal extra\xeddo no es un n\xfamero v\xe1lido."),
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
                    _("La tasa de IVA extra\xedda no es un n\xfamero v\xe1lido."),
                    iva_rate,
                )
            elif rate < 0:
                add(
                    'parsing_error',
                    'iva_rate',
                    _("La tasa de IVA extra\xedda no puede ser negativa."),
                    iva_rate,
                )
            elif 0 < rate < 0.16 and abs(rate - 0.08) >= 1e-6:
                add(
                    'parsing_error',
                    'iva_rate',
                    _(
                        "La tasa de IVA extra\xedda no corresponde a 16 %, 8 % "
                        "ni 0 %; revise las bases manualmente."
                    ),
                    iva_rate,
                )
            elif rate > 1.0:
                add(
                    'parsing_error',
                    'iva_rate',
                    _("La tasa de IVA extra\xedda supera el 100 %; verifique el dato."),
                    iva_rate,
                )

        rif = extracted.get('supplier_rif')
        if rif and not self.env['l10n.ve.import.wizard']._validate_rif(rif):
            add(
                'invalid_rif',
                'supplier_rif',
                _("El RIF extra\xeddo no es v\xe1lido (d\xedgito de control incorrecto)."),
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
            'name': _('Factura F\xedsica R\xe1pida'),
            'res_model': 'l10n.ve.physical.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': defaults,
        }
