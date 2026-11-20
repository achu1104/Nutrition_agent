
import os
import json
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
from groq import Groq
from dotenv import load_dotenv

# Load API key
load_dotenv(Path(__file__).resolve().parent / ".env")

api_key = os.getenv("GROQ_API_KEY")

st.set_page_config(
    page_title="Nutrition AI Dashboard",
    layout="wide"
)

st.title("Nutrition AI Analysis Dashboard")

if not api_key:
    st.error("Please configure GROQ_API_KEY in .env")
    st.stop()

client = Groq(api_key=api_key)

# User information
st.sidebar.header("User Information")

age = st.sidebar.number_input(
    "Age", min_value=1, value=22
)

weight = st.sidebar.number_input(
    "Weight (kg)", min_value=1.0, value=60.0
)

height = st.sidebar.number_input(
    "Height (cm)", min_value=1.0, value=160.0
)

goal = st.sidebar.selectbox(
    "Goal",
    ["Maintain Weight", "Weight Loss", "Weight Gain"]
)

diet = st.sidebar.selectbox(
    "Food Preference",
    ["Vegetarian", "Non-Vegetarian", "Vegan"]
)

allergies = st.sidebar.text_input(
    "Food allergies (optional)"
)

st.header("Daily Food Intake")

breakfast = st.text_input(
    "Breakfast",
    "2 idlis and 1 cup sambar"
)

lunch = st.text_input(
    "Lunch",
    "1 cup rice, 1 cup dal, vegetables"
)

dinner = st.text_input(
    "Dinner",
    "2 chapatis and 1 cup vegetable curry"
)

snacks = st.text_input(
    "Snacks",
    "1 banana and 10 almonds"
)

# BMI
bmi = weight / ((height / 100) ** 2)

if st.button("Analyze My Nutrition"):

    with st.spinner("Analyzing nutrition..."):

        prompt = f"""
        Analyze this person's daily food intake.

        Age: {age}
        Weight: {weight} kg
        Height: {height} cm
        BMI: {bmi:.2f}
        Goal: {goal}
        Diet: {diet}
        Allergies: {allergies or "Not specified"}

        Breakfast: {breakfast}
        Lunch: {lunch}
        Dinner: {dinner}
        Snacks: {snacks}

        Estimate the total daily nutrition.
        Assume typical portions only where missing.
        Make it clear estimates are approximate.
        Never recommend foods containing stated allergens.

        Return ONLY a valid JSON object with:
        calories: number
        protein: number (grams)
        carbs: number (grams)
        fat: number (grams)
        fiber: number (grams)
        analysis: string
        recommendations: array of strings

        Do not include markdown code fences.
        """

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a nutrition analysis assistant. "
                            "Provide approximate estimates, not medical advice. "
                            "Return valid JSON only."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            data = json.loads(
                response.choices[0].message.content
            )

            st.subheader("Nutrition Summary")

            c1, c2, c3, c4 = st.columns(4)

            c1.metric("BMI", f"{bmi:.2f}")
            c2.metric("Calories", f"{data['calories']} kcal")
            c3.metric("Protein", f"{data['protein']} g")
            c4.metric("Fiber", f"{data['fiber']} g")

            st.subheader("Macronutrient Analysis")

            df = pd.DataFrame({
                "Nutrient": ["Protein", "Carbs", "Fat"],
                "Grams": [
                    data["protein"],
                    data["carbs"],
                    data["fat"]
                ]
            })

            fig = px.bar(
                df,
                x="Nutrient",
                y="Grams",
                color="Nutrient",
                title="Daily Macronutrient Intake"
            )

            st.plotly_chart(fig, use_container_width=True)

            # Macro calorie distribution
            macro_df = pd.DataFrame({
                "Nutrient": ["Protein", "Carbs", "Fat"],
                "Calories": [
                    data["protein"] * 4,
                    data["carbs"] * 4,
                    data["fat"] * 9
                ]
            })

            pie = px.pie(
                macro_df,
                names="Nutrient",
                values="Calories",
                title="Estimated Macronutrient Calorie Distribution"
            )

            st.plotly_chart(pie, use_container_width=True)

            st.subheader("AI Nutrition Analysis")
            st.write(data["analysis"])

            st.subheader("Recommendations")

            for recommendation in data["recommendations"]:
                st.success(recommendation)

            st.info(
                "All nutrient values are AI estimates. "
                "Use verified nutrition databases for accurate tracking."
            )

        except Exception as e:
            st.error(
                "Analysis failed. Check your Groq API "
                "connection and returned data."
            )
            st.caption(f"Technical details: {e}")
