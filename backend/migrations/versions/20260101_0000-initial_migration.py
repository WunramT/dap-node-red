"""Initial migration - base tables for authentication.

Revision ID: 20260101_0000
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260101_0000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('entra_group_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_roles_name', 'roles', ['name'], unique=True)

    # Create person table
    op.create_table(
        'person',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('entra_object_id', sa.String(255), nullable=True, unique=True),
        sa.Column('auth_source', sa.String(50), nullable=True, default='local'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        # Soft delete columns (from SoftDeleteMixin)
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deletion_reason', sa.String(500), nullable=True),
    )
    op.create_index('idx_person_email', 'person', ['email'], unique=True)
    op.create_index('idx_person_last_name', 'person', ['last_name'])
    op.create_index('idx_person_is_active', 'person', ['is_active'])
    op.create_index('idx_person_auth_source', 'person', ['auth_source'])
    op.create_index('idx_person_entra_object_id', 'person', ['entra_object_id'], unique=True)

    # Add self-referencing FK for deleted_by after person table exists
    op.create_foreign_key(
        'fk_person_deleted_by',
        'person', 'person',
        ['deleted_by'], ['id'],
        ondelete='SET NULL'
    )

    # Create person_roles junction table
    op.create_table(
        'person_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('person_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('person.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('person_id', 'role_id', name='uq_person_role'),
    )
    op.create_index('ix_person_roles_person_id', 'person_roles', ['person_id'])
    op.create_index('ix_person_roles_role_id', 'person_roles', ['role_id'])

    # Insert default roles
    op.execute("""
        INSERT INTO roles (id, name, description)
        VALUES
            (gen_random_uuid(), 'admin', 'Administrator with full access'),
            (gen_random_uuid(), 'user', 'Standard user with basic access')
    """)


def downgrade() -> None:
    op.drop_table('person_roles')
    op.drop_constraint('fk_person_deleted_by', 'person', type_='foreignkey')
    op.drop_table('person')
    op.drop_table('roles')
