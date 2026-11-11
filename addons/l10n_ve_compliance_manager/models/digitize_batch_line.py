"""Batch receipt lines for the digitize wizard (spec 007 - plan B).

One ``l10n.ve.digitize.batch.line`` per uploaded receipt. Up to
``BATCH_MAX_LINES`` lines are analyzed by ``action_digitize_batch``; item
failures live on the line itself and never abort the rest of the batch.
"""

import base64
import json

from odoo import _, fields, models
from odoo.exceptions import UserError

from .digitize_client import DIGITIZE_ALLOWED_EXTENSIONS

BATCH_MAX_LINES = 20


def image_base64(value):
    """Normalize the Binary value to a plain base64 string (no ``data:``)."""
    if isinstance(value, bytes):
        try:
            value = value.decode('ascii')
        except UnicodeDecodeError:
            # Raw binary payload: encode it instead of dropping it.
            return base64.b64encode(value).decode('ascii')
    value = (value or '').strip()
    if value.startswith('data:'):
        value = value.split(',', 1)[-1]
    return value


def image_bytes(value):
    """Raw bytes of the binary value; ``b''`` when absent or undecodable."""
    if not value:
        return b''
    try:
        return base64.b64decode(image_base64(value), validate=False)
    except (ValueError, TypeError):
        return b''


def extension_from_filename(filename):
    """Lowercase file extension (``'.jpg'``) or ``''`` without a dot."""
    filename = (filename or '').strip()
    if '.' not in filename:
        return ''
    return '.' + filename.rsplit('.', 1)[-1].lower()


def extension_from_bytes(value):
    """Deduce the extension from the magic bytes of the image."""
    data = image_bytes(value)[:12]
    if not data:
        return ''
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return '.webp'
    return ''


def resolve_extension(filename, value):
    """Extension from the filename when usable, from magic bytes otherwise."""
    return extension_from_filename(filename) or extension_from_bytes(value)


def image_size_mb(value):
    """Size of the decoded image in MB."""
    return len(image_bytes(value)) / (1024 * 1024)


def payload_filename(filename, value):
    """Filename to send to the service: always a non-empty ``str``."""
    filename = (filename or '').strip()
    if filename:
        return filename
    return 'invoice' + (resolve_extension(filename, value) or '.jpg')


def validate_image(value, filename, max_mb, allowed=DIGITIZE_ALLOWED_EXTENSIONS):
    """Validate presence, format and size; raises ``ValueError`` on failure.

    Reuses the same user-facing texts as the single-image flow so the
    accountant sees the same message in both paths.
    """
    if not value:
        raise ValueError(_("Adjunte una imagen de la factura antes de analizar."))
    extension = resolve_extension(filename, value)
    if extension not in allowed:
        raise ValueError(
            _("Formato no soportado. Se aceptan im\xe1genes JPG, JPEG, PNG o WEBP.")
        )
    size_mb = image_size_mb(value)
    if size_mb > max_mb:
        raise ValueError(
            _(
                "La imagen pesa %.1f MB y supera el l\xedmite de %.1f MB. "
                "Reduzca su tama\xf1o antes de analizar."
            )
            % (size_mb, max_mb)
        )


class DigitizeBatchLine(models.TransientModel):
    _name = 'l10n.ve.digitize.batch.line'
    _description = 'Recibo del lote de digitalizaci\xf3n'
    _order = 'id'
    _rec_name = 'filename'

    wizard_id = fields.Many2one(
        'l10n.ve.digitize.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    image = fields.Binary(string='Imagen del recibo', attachment=True)
    filename = fields.Char(string='Nombre del archivo')
    status = fields.Selection(
        [
            ('pending', 'Pendiente'),
            ('done', 'Analizado'),
            ('error', 'Error'),
        ],
        string='Estado',
        default='pending',
        readonly=True,
    )
    error_message = fields.Char(string='Mensaje de Error', readonly=True)
    result_json = fields.Text(string='Resultado (JSON)', readonly=True)

    def _build_payload(self, document_type, max_mb):
        """Contract payload for this receipt; raises ``ValueError`` if invalid."""
        validate_image(self.image, self.filename, max_mb)
        return {
            'image_base64': image_base64(self.image),
            'filename': payload_filename(self.filename, self.image),
            'document_type': document_type or 'auto',
        }

    def action_apply_line_to_invoice(self):
        """Abre Factura Física Rápida con los datos de esta fila (spec 007-D).

        Read-only: no ``create``/``write``/``sudo``. The mapping itself is
        delegated to the wizard helper so the single and batch flows share
        one contract (RF-D-05).
        """
        self.ensure_one()

        if self.status == 'pending':
            raise UserError(_("Analice el recibo antes de usar los datos."))
        if self.status != 'done':
            raise UserError(
                _(
                    "El recibo tiene un error de an\xe1lisis. "
                    "Corr\xedjalo o reanal\xedcelo antes de usar los datos."
                )
            )

        try:
            data = json.loads(self.result_json or '')
        except (TypeError, ValueError):
            data = None

        extracted = data.get('extracted') if isinstance(data, dict) else None
        if not isinstance(extracted, dict) or not extracted:
            raise UserError(
                _("El recibo no tiene datos analizados. Vuelva a analizarlo.")
            )

        return self.wizard_id._build_apply_to_invoice_action(
            extracted,
            document_type=data.get('document_type'),
            confidence=data.get('confidence'),
        )
