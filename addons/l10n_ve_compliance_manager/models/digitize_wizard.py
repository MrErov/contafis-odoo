import base64
import logging
import time

import requests
from odoo import _, fields, models
from odoo.exceptions import ValidationError

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
            return float(self._get_param('l10n_ve_digitize.timeout_seconds', '30') or 30)
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

        if (
            not isinstance(data, dict)
            or not data.get('document_type')
            or 'confidence' not in data
            or not isinstance(data.get('extracted'), dict)
        ):
            return self._set_error(
                _(
                    "⚠️ La respuesta del servicio está incompleta. "
                    "Reintentá o cargue la factura a mano."
                )
            )

        try:
            confidence = float(data.get('confidence'))
        except (TypeError, ValueError):
            return self._set_error(
                _(
                    "⚠️ La respuesta del servicio está incompleta. "
                    "Reintentá o cargue la factura a mano."
                )
            )

        self.write(
            {
                'state': 'done',
                'error_message': False,
                'confidence': min(max(confidence, 0.0), 1.0),
                'detected_document_type': str(data['document_type']),
            }
        )
        return self._reload_action()
