from tortoise import fields, models

class IndexHistoricalData(models.Model):
    """
    Model to store daily historical data for indices like NIFTY50.
    """
    id = fields.IntField(pk=True)
    symbol = fields.CharField(max_length=30, description="The symbol of the index, e.g., NSE:NIFTY50-INDEX",null= True)
    date = fields.DateField(description="The date of the historical data", null=True)
    open = fields.FloatField(description="Opening price for the day", null=True)
    high = fields.FloatField(description="Highest price for the day",null=True)
    low = fields.FloatField(description="Lowest price for the day",null=True)
    close = fields.FloatField(description="Closing price for the day",null=True)
    volume = fields.BigIntField(description="Trading volume for the day",null=True)

    class Meta:
        table = "index_historical_data"
        # Ensures that for a given symbol, there's only one entry per date.
        unique_together = ("symbol", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.symbol} on {self.date}: Close {self.close}"