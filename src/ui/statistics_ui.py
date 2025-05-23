from src.dal.preds import read_data
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import streamlit as st
import folium


def country_statistics(pred, country):
    locations = len(pred["id_bbox"].unique())
    inter = pred.sjoin(country, how="left")
    countries_cnt = inter.groupby("name").count()
    countries_cnt["Trees_Detected"] = countries_cnt["id"]
    return countries_cnt, locations


def init_statistics(config):
    st.header("Statistics :bar_chart:")
    with st.container():
        cols = st.columns(2)
        with cols[1]:
            pred, country = read_data()
            countries_cnt, locations = country_statistics(pred, country)
            st.metric("Ran in countries", len(countries_cnt))
            st.metric(
                "Total coconut trees detected", countries_cnt["Trees_Detected"].sum()
            )
            st.metric("Total locations covered", locations)
        with cols[0]:
            m = folium.Map()
            pred["latitude"], pred["longitude"] = pred.geometry.x, pred.geometry.y
            heat_data = pred[["longitude", "latitude"]].values.tolist()

            HeatMap(
                heat_data,
                radius=config["statistics_ui"]["heatmap"]["radius"],
                blur=config["statistics_ui"]["heatmap"]["blur"],
            ).add_to(m)

            st_folium(
                m,
                use_container_width=True,
                center=config["statistics_ui"]["center"],
                zoom=config["statistics_ui"]["zoom"],
            )
        st.dataframe(countries_cnt["Trees_Detected"])
