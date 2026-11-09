"""add transcript chunks

Revision ID: 3a8c5d2e1f40
Revises: 11fb9f7925ae
Create Date: 2026-11-07 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a8c5d2e1f40'
down_revision: Union[str, Sequence[str], None] = '11fb9f7925ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'transcript_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('recording_id', sa.Integer(), nullable=True),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('speaker_label', sa.String(length=100), nullable=True),
        sa.Column('start_time', sa.Double(), nullable=False),
        sa.Column('end_time', sa.Double(), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recording_id'], ['recordings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transcript_chunks_id'), 'transcript_chunks', ['id'], unique=False)
    op.create_index(op.f('ix_transcript_chunks_meeting_id'), 'transcript_chunks', ['meeting_id'], unique=False)
    op.create_index(op.f('ix_transcript_chunks_recording_id'), 'transcript_chunks', ['recording_id'], unique=False)
    op.create_index(op.f('ix_transcript_chunks_start_time'), 'transcript_chunks', ['start_time'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_transcript_chunks_start_time'), table_name='transcript_chunks')
    op.drop_index(op.f('ix_transcript_chunks_recording_id'), table_name='transcript_chunks')
    op.drop_index(op.f('ix_transcript_chunks_meeting_id'), table_name='transcript_chunks')
    op.drop_index(op.f('ix_transcript_chunks_id'), table_name='transcript_chunks')
    op.drop_table('transcript_chunks')
