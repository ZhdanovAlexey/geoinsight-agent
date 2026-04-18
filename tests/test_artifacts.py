from backend.api.schemas import ChartArtifact, MapArtifact, TableArtifact


def test_map_artifact_defaults():
    art = MapArtifact()
    assert art.type == "map"
    assert art.viz == "choropleth"
    assert art.geojson == {}


def test_table_artifact():
    art = TableArtifact(
        title="Test",
        columns=["a", "b"],
        rows=[[1, 2], [3, 4]],
    )
    assert art.type == "table"
    assert len(art.rows) == 2


def test_chart_artifact():
    art = ChartArtifact(
        chart_type="bar",
        title="Traffic",
        data={"labels": ["00:00", "01:00"], "values": [10, 20]},
    )
    assert art.type == "chart"
    assert art.data["values"] == [10, 20]
