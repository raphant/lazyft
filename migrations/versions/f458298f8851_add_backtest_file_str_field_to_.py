"""Add backtest_file_str field to BacktestReport

Revision ID: f458298f8851
Revises: b9fc1ff6b2ff
Create Date: 2022-05-26 05:29:46.360483

"""
from alembic import op
import sqlalchemy as sa
from sqlmodel import SQLModel  # NEW
import sqlmodel.sql.sqltypes  # NEW


# revision identifiers, used by Alembic.
revision = 'f458298f8851'
down_revision = 'b9fc1ff6b2ff'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
