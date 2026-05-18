import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import time


def build_cohort_matrix(df):
    # Extract order month and cohort month
    df["order_month"] = df["order_purchase_timestamp"].dt.to_period("M")
    df["cohort_month"] = df.groupby("customer_id")["order_month"].transform("min")

    # Calculate period index (difference in months)
    df["period"] = df["order_month"].astype(int) - df["cohort_month"].astype(int)

    # Count unique customers per cohort-period
    cohort_data = (
        df.groupby(["cohort_month", "period"])["customer_id"].nunique().reset_index()
    )

    # Pivot into matrix
    cohort_matrix = cohort_data.pivot(
        index="cohort_month", columns="period", values="customer_id"
    )

    # Normalize to retention rates
    cohort_matrix = cohort_matrix.divide(cohort_matrix.iloc[:, 0], axis=0)

    return cohort_matrix


# -----------------------------
# Data Loading with Caching
# -----------------------------
@st.cache_data
def load_data():
    return pd.read_csv(
        "../data/cleaned_olist_data.csv", parse_dates=["order_purchase_timestamp"]
    )


t0 = time.time()
df = load_data()
st.sidebar.info(f"Loaded in {time.time()-t0:.3f}s (cached)")

rfm_df = pd.read_csv("../data/rfm.csv")
cohort_matrix = pd.read_csv("../data/df_cohort.csv", index_col=0)

# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.title("E‑Commerce Dashboard")
with st.sidebar.expander("Dataset Info"):
    st.write(f"Shape: {df.shape}")
    st.write(
        f"Date Range: {df['order_purchase_timestamp'].min()} → {df['order_purchase_timestamp'].max()}"
    )

date_range = st.sidebar.date_input(
    "Global Date Range",
    [df["order_purchase_timestamp"].min(), df["order_purchase_timestamp"].max()],
)

page = st.sidebar.selectbox(
    "Navigate",
    [
        "Overview",
        "Sales",
        "Delivery",
        "Customers",
        "Simulator",
        "Sunburst",
        "Bubble Animation",
        "Cohort Heatmap",
        "Seller Quadrant",
        "Funnel",
        "RFM 3D",
        "Sankey",
    ],
)

# -----------------------------
# Overview Page
# -----------------------------
if page == "Overview":
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue (BRL)", f"R$ {df['price'].sum():,.0f}", "+5.2%")
    col2.metric("Total Orders", f"{df['order_id'].nunique():,}", "+3.1%")
    col3.metric("Avg Order Value", f"R$ {df['price'].mean():.2f}", "-1.4%")
    col4.metric("Avg Review Score", f"{df['review_score'].mean():.2f}", "+0.3")

    fig = px.pie(df, names="order_status", hole=0.45)
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Sales Analysis Page
# -----------------------------
elif page == "Sales":
    all_cats = df["category_en"].dropna().unique().tolist()
    cats = st.multiselect("Categories", all_cats, default=all_cats[:10])
    filtered = df[df["category_en"].isin(cats)]

    st.plotly_chart(
        px.bar(
            filtered.groupby("category_en")["price"].sum().nlargest(15).reset_index(),
            x="category_en",
            y="price",
        ),
        use_container_width=True,
    )

    monthly_rev = (
        df.groupby(df["order_purchase_timestamp"].dt.to_period("M"))["price"]
        .sum()
        .reset_index()
    )
    monthly_rev["order_purchase_timestamp"] = monthly_rev[
        "order_purchase_timestamp"
    ].astype(str)
    st.plotly_chart(
        px.line(monthly_rev, x="order_purchase_timestamp", y="price"),
        use_container_width=True,
    )

    st.plotly_chart(
        px.scatter(
            filtered, x="price", y="freight_value", color="category_en", opacity=0.5
        ),
        use_container_width=True,
    )

    with st.expander("View Data"):
        st.dataframe(filtered)

# -----------------------------
# Delivery & Logistics Page
# -----------------------------
elif page == "Delivery":
    option = st.selectbox("View", ["Maps", "Charts"])
    if option == "Maps":
        state_df = (
            df.groupby("customer_state")["delivery_delay_days"].mean().reset_index()
        )
        fig = px.choropleth(
            state_df,
            locations="customer_state",
            color="delivery_delay_days",
            locationmode="ISO-3",
            scope="south america",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.plotly_chart(
            px.box(df, x="customer_state", y="delivery_delay_days"),
            use_container_width=True,
        )

# -----------------------------
# Customer Intelligence Page
# -----------------------------
elif page == "Customers":
    st.plotly_chart(
        px.scatter(
            rfm_df,
            x="recency",
            y="monetary",
            color="frequency",
            size="monetary",
            color_continuous_scale="Viridis",
        ),
        use_container_width=True,
    )

    st.plotly_chart(
        px.bar(
            rfm_df["RFM_segment"].value_counts().reset_index(),
            x="RFM_segment",
            y="RFM_segment",
        ),
        use_container_width=True,
    )

    min_orders = st.slider("Min. Orders", 1, 10, 2)
    filtered_top = rfm_df[rfm_df["frequency"] >= min_orders].nlargest(20, "monetary")
    st.dataframe(filtered_top, use_container_width=True)

# -----------------------------
# What‑If Simulator Page
# -----------------------------
elif page == "Simulator":
    base_revenue = df["price"].sum()
    base_review = df["review_score"].mean()

    multiplier = st.slider("Freight Cost Multiplier", 0.5, 2.0, 1.0)
    delay_adj = st.slider("Avg Delay Adjustment (days)", -5, 5, 0)

    adj_revenue = base_revenue * (1 - (multiplier - 1) * 0.15)
    review_change = delay_adj * -0.05  # Example correlation coefficient
    adj_review = base_review + review_change

    col1, col2 = st.columns(2)
    col1.metric(
        "Projected Revenue",
        f"R$ {adj_revenue:,.0f}",
        f"{(adj_revenue/base_revenue-1)*100:+.1f}%",
    )
    col2.metric("Projected Review Score", f"{adj_review:.2f}", f"{review_change:+.2f}")

# -----------------------------
# Advanced Visualisations Q29–35
# -----------------------------


elif page == "Sunburst":
    fig = px.sunburst(
        df,
        path=["region", "customer_state", "category_en"],
        values="price",
        color="price",
        color_continuous_scale="RdBu",
    )
    fig.write_html("../assets/sunburst.html")
    st.plotly_chart(fig, use_container_width=True)

elif page == "Bubble Animation":
    df["month_year"] = df["order_purchase_timestamp"].dt.strftime("%Y-%m")
    monthly = (
        df.groupby(["customer_state", "month_year"])
        .agg(
            orders=("order_id", "nunique"),
            avg_review=("review_score", "mean"),
            total_price=("price", "sum"),
        )
        .reset_index()
    )
    fig = px.scatter(
        monthly,
        x="orders",
        y="avg_review",
        size="total_price",
        color="customer_state",
        animation_frame="month_year",
        range_y=[1, 5],
    )
    st.plotly_chart(fig, use_container_width=True)

elif page == "Cohort Heatmap":
    heatmap_data = build_cohort_matrix(df).iloc[:, :12].copy()

    # Format labels
    heatmap_data.index = heatmap_data.index.astype(str)
    heatmap_data.columns = [f"Period {i+1}" for i in range(len(heatmap_data.columns))]

    # Plot heatmap
    fig = px.imshow(heatmap_data, color_continuous_scale="RdYlGn", text_auto=".0%")
    fig.update_layout(xaxis_title="Period", yaxis_title="Cohort Month")
    st.plotly_chart(fig, use_container_width=True)


elif page == "Seller Quadrant":
    seller_df = (
        df.groupby("seller_id")
        .agg(
            avg_review=("review_score", "mean"),
            on_time=("delivery_delay_days", "mean"),
            revenue=("price", "sum"),
            customers=("customer_id", "nunique"),
        )
        .reset_index()
    )
    median_score = seller_df["avg_review"].median()
    median_ontime = seller_df["on_time"].median()
    fig = px.scatter(
        seller_df,
        x="avg_review",
        y="on_time",
        size="revenue",
        color="customers",
        hover_data=["seller_id"],
    )
    fig.add_vline(x=median_score, line_dash="dash", line_color="gray")
    fig.add_hline(y=median_ontime, line_dash="dash", line_color="gray")
    st.plotly_chart(fig, use_container_width=True)

elif page == "Funnel":
    stages = {
        "Placed": len(df),
        "Approved": len(df[df["order_status"] == "approved"]),
        "Shipped": len(df[df["order_status"] == "shipped"]),
        "Delivered": len(df[df["order_status"] == "delivered"]),
        "Reviewed ≥4": len(df[df["review_score"] >= 4]),
    }
    stages_df = pd.DataFrame({"stage": stages.keys(), "count": stages.values()})
    fig = px.funnel(stages_df, x="count", y="stage")
    st.plotly_chart(fig, use_container_width=True)

elif page == "RFM 3D":
    fig = px.scatter_3d(
        rfm_df,
        x="recency",
        y="frequency",
        z="monetary",
        color="RFM_segment",
        opacity=0.7,
        size_max=8,
    )
    fig.update_layout(
        scene=dict(
            xaxis_title="Recency (days)",
            yaxis_title="Frequency",
            zaxis_title="Monetary",
        )
    )
    fig.write_html("../assets/rfm3d.html")
    st.plotly_chart(fig, use_container_width=True)

elif page == "Sankey":

    # Limit to top categories and payments
    top_payments = df["payment_type"].value_counts().nlargest(3).index
    top_cats = df["category_en"].value_counts().nlargest(5).index
    sankey_df = df[
        df["payment_type"].isin(top_payments) & df["category_en"].isin(top_cats)
    ]

    # Derive delivery outcome if not present
    if "delivery_outcome" not in sankey_df.columns:
        sankey_df["delivery_outcome"] = sankey_df["delivery_delay_days"].apply(
            lambda x: "On-time" if x <= 0 else "Late"
        )

    # Define nodes
    nodes = list(top_payments) + list(top_cats) + ["On-time", "Late"]
    node_map = {n: i for i, n in enumerate(nodes)}

    # Build links
    sources, targets, values = [], [], []
    for p in top_payments:
        for c in top_cats:
            subset = sankey_df[
                (sankey_df["payment_type"] == p) & (sankey_df["category_en"] == c)
            ]
            if len(subset) > 0:
                # Payment → Category
                sources.append(node_map[p])
                targets.append(node_map[c])
                values.append(len(subset))
                # Category → Outcome
                for outcome in ["On-time", "Late"]:
                    val = len(subset[subset["delivery_outcome"] == outcome])
                    if val > 0:
                        sources.append(node_map[c])
                        targets.append(node_map[outcome])
                        values.append(val)

    if values:  # Only plot if we have data
        fig = go.Figure(
            go.Sankey(
                node=dict(label=nodes, pad=15, thickness=20),
                link=dict(source=sources, target=targets, value=values),
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data available for Sankey diagram with current filters.")
