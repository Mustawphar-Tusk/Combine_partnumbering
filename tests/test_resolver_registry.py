from src.configuration_engine.resolvers import ResolverRegistry


class Resolver:
    def resolve(self, **kwargs):
        return None


def test_resolver_registry() -> None:
    registry = ResolverRegistry()
    resolver = Resolver()

    registry.register("ATTRIBUTE", resolver)

    assert registry.get("attribute") is resolver
