class RAGService:
    def __init__(self):
        pass

    async def search_related_concepts(self, query: str):
        """
        Queries Qdrant for related concept cards.
        """
        # TODO: Implement Qdrant client call
        return [
            {"title": "Projectile Motion", "id": "PHYS-101", "score": 0.95},
            {"title": "Kinematic Equations", "id": "PHYS-102", "score": 0.88}
        ]

rag_service = RAGService()
