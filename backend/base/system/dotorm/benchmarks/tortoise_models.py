"""Tortoise ORM models for benchmarks.

These models are used in Tortoise ORM benchmark tests.
"""

try:
    from tortoise import fields
    from tortoise.models import Model

    class BenchmarkRole(Model):
        """Role model for Tortoise ORM benchmarks."""
        
        id = fields.IntField(pk=True)
        name = fields.CharField(max_length=100)
        description = fields.CharField(max_length=255, null=True)
        
        class Meta:
            table = "benchmark_roles"


    class BenchmarkUser(Model):
        """User model for Tortoise ORM benchmarks."""
        
        id = fields.IntField(pk=True)
        name = fields.CharField(max_length=100)
        email = fields.CharField(max_length=255)
        active = fields.BooleanField(default=True)
        role = fields.ForeignKeyField(
            "models.BenchmarkRole",
            related_name="users",
            null=True,
        )
        
        class Meta:
            table = "benchmark_users"

except ImportError:
    # Tortoise not installed, create placeholder classes
    class BenchmarkRole:
        pass
    
    class BenchmarkUser:
        pass
