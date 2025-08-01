"""Add is_public and user_id to Exercise

Revision ID: 21671067d6b3
Revises: 85c2fd1463aa
Create Date: 2025-08-02 13:55:30.733507

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '21671067d6b3'
down_revision = '85c2fd1463aa'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('exercise', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_public', sa.Boolean(), nullable=True, server_default=sa.sql.expression.true()))
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_exercise_user_id_user', 'user', ['user_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('exercise', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('user_id')
        batch_op.drop_column('is_public')

    # ### end Alembic commands ###
