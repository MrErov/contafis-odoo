from datetime import timedelta

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestChatHistoryModel(TransactionCase):
    """Tests del modelo l10n.ve.chat.history (historial de chat Asistente Fiscal)."""

    def setUp(self):
        super().setUp()
        self.ChatHistory = self.env['l10n.ve.chat.history']
        self.User = self.env['res.users']
        self.Company = self.env['res.company']

        # Crear dos empresas
        self.company_a = self.Company.create({'name': 'Empresa A'})
        self.company_b = self.Company.create({'name': 'Empresa B'})

        # Crear usuario contador para Empresa A
        self.accountant_a = self.User.create({
            'name': 'Contador A',
            'login': 'contador_a',
            'email': 'contador_a@test.com',
            'company_id': self.company_a.id,
            'company_ids': [(4, self.company_a.id)],
            'group_ids': [(6, 0, [
                self.env.ref('account.group_account_user').id,
                self.env.ref('l10n_ve_compliance_manager.l10n_ve_compliance_accountant').id,
            ])],
        })

        # Crear usuario contador para Empresa B
        self.accountant_b = self.User.create({
            'name': 'Contador B',
            'login': 'contador_b',
            'email': 'contador_b@test.com',
            'company_id': self.company_b.id,
            'company_ids': [(4, self.company_b.id)],
            'group_ids': [(6, 0, [
                self.env.ref('account.group_account_user').id,
                self.env.ref('l10n_ve_compliance_manager.l10n_ve_compliance_accountant').id,
            ])],
        })

        # Admin (ve todo) - añadir a las empresas de prueba para acceso
        self.admin = self.env.ref('base.user_admin')
        self.admin.write({'group_ids': [(4, self.env.ref('base.group_system').id)]})
        # Añadir admin a las empresas de prueba para acceso a mensajes
        (self.company_a + self.company_b).write({'user_ids': [(4, self.admin.id)]})

    def test_create_message(self):
        """Crear mensaje de usuario y asistente, verifica campos."""
        msg_user = self.ChatHistory.with_user(self.accountant_a).create({
            'user_id': self.accountant_a.id,
            'company_id': self.company_a.id,
            'conversation_id': 'conv-test-001',
            'role': 'user',
            'content': '¿Cuál es el vencimiento IVA?',
            'warnings': [],
        })
        self.assertEqual(msg_user.role, 'user')
        self.assertEqual(msg_user.content, '¿Cuál es el vencimiento IVA?')
        # Json field vacío puede retornar [] o False en Odoo
        self.assertIn(msg_user.warnings, ([], False))
        self.assertEqual(msg_user.company_id, self.company_a)
        self.assertEqual(msg_user.create_uid, self.accountant_a)

        msg_assistant = self.ChatHistory.with_user(self.accountant_a).create({
            'user_id': self.accountant_a.id,
            'company_id': self.company_a.id,
            'conversation_id': 'conv-test-001',
            'role': 'assistant',
            'content': 'El vencimiento IVA es el día 15...',
            'warnings': ['scope_admin_key'],
        })
        self.assertEqual(msg_assistant.role, 'assistant')
        self.assertEqual(msg_assistant.warnings, ['scope_admin_key'])

    def test_multi_company_isolation(self):
        """Contador A no ve mensajes de Contador B (distinta empresa)."""
        # Mensaje de Contador A en Empresa A
        self.ChatHistory.with_user(self.accountant_a).create({
            'user_id': self.accountant_a.id,
            'company_id': self.company_a.id,
            'conversation_id': 'conv-a-001',
            'role': 'user',
            'content': 'Mensaje Empresa A',
            'warnings': [],
        })

        # Mensaje de Contador B en Empresa B
        self.ChatHistory.with_user(self.accountant_b).create({
            'user_id': self.accountant_b.id,
            'company_id': self.company_b.id,
            'conversation_id': 'conv-b-001',
            'role': 'user',
            'content': 'Mensaje Empresa B',
            'warnings': [],
        })

        # Contador A solo ve sus mensajes
        msgs_a = self.ChatHistory.with_user(self.accountant_a).search([])
        self.assertEqual(len(msgs_a), 1)
        self.assertEqual(msgs_a.content, 'Mensaje Empresa A')

        # Contador B solo ve sus mensajes
        msgs_b = self.ChatHistory.with_user(self.accountant_b).search([])
        self.assertEqual(len(msgs_b), 1)
        self.assertEqual(msgs_b.content, 'Mensaje Empresa B')

    def test_admin_sees_all(self):
        """Admin ve mensajes de todas las empresas."""
        self.ChatHistory.with_user(self.accountant_a).create({
            'user_id': self.accountant_a.id,
            'company_id': self.company_a.id,
            'conversation_id': 'conv-a-001',
            'role': 'user',
            'content': 'Msg A',
            'warnings': [],
        })
        self.ChatHistory.with_user(self.accountant_b).create({
            'user_id': self.accountant_b.id,
            'company_id': self.company_b.id,
            'conversation_id': 'conv-b-001',
            'role': 'user',
            'content': 'Msg B',
            'warnings': [],
        })

        msgs_admin = self.ChatHistory.with_user(self.admin).search([])
        self.assertEqual(len(msgs_admin), 2)

def test_conversation_order_by_create_date(self):
        """Conversación más reciente por create_date del primer mensaje."""
        from datetime import datetime

        # Primera conversación (más antigua)
        old_date = datetime.now() - timedelta(seconds=30)
        self.ChatHistory.with_user(self.accountant_a).create({
            'user_id': self.accountant_a.id,
            'company_id': self.company_a.id,
            'conversation_id': 'conv-old',
            'role': 'user',
            'content': 'Old',
            'warnings': [],
            'create_date': old_date.strftime('%Y-%m-%d %H:%M:%S'),
        })

        # Segunda conversación (más reciente)
        new_date = datetime.now() + timedelta(seconds=10)
        self.ChatHistory.with_user(self.accountant_a).create({
            'user_id': self.accountant_a.id,
            'company_id': self.company_a.id,
            'conversation_id': 'conv-new',
            'role': 'user',
            'content': 'New',
            'warnings': [],
            'create_date': new_date.strftime('%Y-%m-%d %H:%M:%S'),
        })

        # Buscar última conversación (por create_date del primer mensaje)
        last_conv = self.ChatHistory.with_user(self.accountant_a).search(
            [('company_id', '=', self.company_a.id)],
            order='create_date DESC',
            limit=1,
        )
        self.assertEqual(last_conv.conversation_id, 'conv-new')


@tagged('post_install', '-at_install')
class TestResUsersApiToken(TransactionCase):
    """Tests del campo api_token en res.users."""

    def setUp(self):
        super().setUp()
        self.User = self.env['res.users']
        self.admin = self.env.ref('base.user_admin')

    def test_api_token_field_exists(self):
        """Campo api_token existe en res.users."""
        self.assertIn('api_token', self.User._fields)
        field = self.User._fields['api_token']
        self.assertEqual(field.type, 'char')

    def test_api_token_only_admin_editable(self):
        """Solo admin (base.group_system) puede editar api_token."""
        accountant = self.User.create({
            'name': 'Test Accountant',
            'login': 'test_acct',
            'email': 'test@acct.com',
            'group_ids': [(6, 0, [
                self.env.ref('account.group_account_user').id,
            ])],
        })
        # Admin puede escribir
        self.admin.write({'api_token': 'admin-token-123'})
        self.assertEqual(self.admin.api_token, 'admin-token-123')

        # Contador NO puede escribir (AccessError) - ejecutar como el usuario contador
        with self.assertRaises(AccessError):
            accountant.with_user(accountant).write({'api_token': 'hacker-token'})

        # Contador puede leer (campo visible) - en Odoo, Char vacío retorna False o ''
        self.assertIn(accountant.api_token, ('', False))

    def test_api_token_help_text(self):
        """Campo tiene help descriptivo."""
        field = self.User._fields['api_token']
        self.assertIn('Asistente Fiscal', field.help or '')
