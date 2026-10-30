import base64

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import image as image_tools


class CarteleraEvidence(models.Model):
    _name = 'l10n.ve.cartelera.evidence'
    _description = 'Evidencia de documento para cartelera fiscal'
    _order = 'uploaded_at desc'

    cartelera_status_id = fields.Many2one(
        'l10n.ve.cartelera.status',
        string='Snapshot Cartelera',
        required=True,
        ondelete='cascade',
    )
    filename = fields.Char(string='Nombre del archivo')
    image = fields.Binary(
        string='Imagen',
        attachment=True,
    )
    image_128 = fields.Binary(
        string='Imagen 128x128',
        compute='_compute_image_128',
        store=True,
    )
    file_size_mb = fields.Float(
        string='Tamaño (MB)',
        compute='_compute_file_size_mb',
        store=False,
    )
    uploaded_by = fields.Many2one(
        'res.users',
        string='Subido por',
        default=lambda self: self.env.user,
        readonly=True,
    )
    uploaded_at = fields.Datetime(
        string='Fecha de subida',
        default=fields.Datetime.now,
        readonly=True,
    )
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptado'),
        ('rejected', 'Rechazado'),
    ], string='Estado', required=True, default='pending')
    notes = fields.Text(string='Notas')

    @api.depends('image')
    def _compute_image_128(self):
        for rec in self:
            rec.image_128 = image_tools.image_process(rec.image, size=(128, 128)) if rec.image else False

    @api.depends('image')
    def _compute_file_size_mb(self):
        for rec in self:
            if rec.image:
                rec.file_size_mb = len(base64.b64decode(rec.image)) / (1024 * 1024)
            else:
                rec.file_size_mb = 0.0

    @api.model
    def _get_max_size_mb(self):
        """Obtiene el tamaño máximo permitido en MB desde ir.config_parameter."""
        ICP = self.env['ir.config_parameter'].sudo()
        return float(ICP.get_str('l10n_ve_compliance.evidence_max_size_mb', '5.0'))

    @api.constrains('image')
    def _check_image_size(self):
        max_mb = self._get_max_size_mb()
        for rec in self:
            if rec.image and rec.file_size_mb > max_mb:
                raise ValidationError(
                    f"El archivo '{rec.filename or 'sin nombre'}' pesa "
                    f"{rec.file_size_mb:.1f} MB y supera el límite de "
                    f"{max_mb:.1f} MB. Reduce su tamaño antes de subir."
                )

    def _notify_status_recompute(self):
        """Notifica al status asociado que debe recalcular su estado."""
        statuses = self.mapped('cartelera_status_id')
        if statuses:
            statuses._recompute_status_from_evidence()

    @api.model_create_multi
    def create(self, vals_list):
        evidences = super().create(vals_list)
        evidences._notify_status_recompute()
        return evidences

    def write(self, vals):
        # Si cambia el state, notificar recompute
        state_changed = 'state' in vals
        result = super().write(vals)
        if state_changed:
            self._notify_status_recompute()
        return result

    def unlink(self):
        # Mapear statuses antes de borrar
        statuses = self.mapped('cartelera_status_id')
        result = super().unlink()
        # Recomputar en statuses afectados
        if statuses:
            statuses._recompute_status_from_evidence()
        return result
