"""Adapter de fila: despacha tasks para o Celery (RabbitMQ).

Import LAZY do Celery dentro do metodo — quem sobe apenas a API nao
precisa do worker importado, e testes de unidade nao tocam no broker.
"""

from __future__ import annotations

from uuid import UUID

from modules.image_generation.application.ports.task_queue import TaskQueuePort


class CeleryTaskQueue(TaskQueuePort):
    def enqueue_generation(self, generation_id: UUID, *, kind: str = "generate") -> None:
        from infra.settings import get_settings
        from workers.celery_app.limits import task_time_limits
        from workers.celery_app.tasks import process_generation_task

        soft_limit, hard_limit = task_time_limits(kind, get_settings())
        process_generation_task.apply_async(
            args=[str(generation_id), kind],
            queue="generation.standard",
            soft_time_limit=soft_limit,
            time_limit=hard_limit,
        )
