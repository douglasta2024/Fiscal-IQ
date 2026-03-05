import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import _ from "lodash";
import { Responsive } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import NavigationMenu from "../components/NavigationMenu";
import "../App.css";

/* --- 1. CUSTOM WIDTH HANDLER --- */
const withResizeHandler = (Component) => {
  return (props) => {
    const [width, setWidth] = useState(window.innerWidth - 40);

    useEffect(() => {
      const handleResize = () => {
        setWidth(window.innerWidth - 40);
      };

      window.addEventListener("resize", handleResize);
      return () => window.removeEventListener("resize", handleResize);
    }, []);

    return (
      <div style={{ width: '100%', minHeight: '100vh' }}>
        <Component width={width} {...props} />
      </div>
    );
  };
};

const ResponsiveGrid = withResizeHandler(Responsive);

/* --- 2. INTERNAL COMPONENT: EMPTY WIDGET SELECTOR --- */
const EmptyWidgetSelector = ({ onSelect }) => {
  const [showOptions, setShowOptions] = useState(false);

  if (showOptions) {
    return (
      <div className="empty-widget-container">
        <div style={{ marginBottom: 10, fontSize: 12, color: '#aaa' }}>Select Widget Type:</div>
        <div className="widget-type-selector">
          <button className="type-btn" onClick={() => onSelect("price_chart")}>📈 Chart</button>
          <button className="type-btn" onClick={() => onSelect("news_feed")}>📰 News</button>
          <button className="type-btn" onClick={() => onSelect("financials")}>💰 Financials</button>
          <button className="type-btn cancel-btn" onClick={() => setShowOptions(false)}>❌ Cancel</button>
        </div>
      </div>
    );
  }

  return (
    <div className="empty-widget-container">
      {/* Remove the "+" text inside */}
      <button className="big-plus-btn" onClick={() => setShowOptions(true)}></button>
    </div>
  );
};

/* --- 3. MAIN DASHBOARD COMPONENT --- */
const Dashboard = () => {
  // STATE: The list of widgets (Default to square shapes)
  const [items, setItems] = useState([
    { i: "a", x: 0, y: 0, w: 4, h: 11, type: "price_chart" },
    { i: "b", x: 4, y: 0, w: 4, h: 11, type: "news_feed" },
  ]);

  const [openMenuId, setOpenMenuId] = useState(null);

  useEffect(() => {
    const handleClickOutside = () => setOpenMenuId(null);
    window.addEventListener("click", handleClickOutside);
    return () => window.removeEventListener("click", handleClickOutside);
  }, []);

  // ADD NEW WIDGET (Square Default: w=4, h=11)
  const addItem = () => {
    const newId = _.uniqueId("item_");
    setItems([...items, { i: newId, x: 0, y: Infinity, w: 4, h: 11, type: "empty" }]);
  };

  const removeItem = (id) => {
    setItems(items.filter(i => i.i !== id));
    setOpenMenuId(null);
  };

  const changeWidgetType = (id, newType) => {
    setItems((prevItems) =>
      prevItems.map((item) =>
        item.i === id ? { ...item, type: newType } : item
      )
    );
  };

  const onLayoutChange = (layout) => {
    const updatedItems = items.map(item => {
      const layoutItem = layout.find(l => l.i === item.i);
      if (layoutItem) return { ...item, ...layoutItem };
      return item;
    });
    setItems(updatedItems);
  };

  const toggleMenu = (e, id) => {
    e.stopPropagation();
    setOpenMenuId(openMenuId === id ? null : id);
  };

  const renderWidgetContent = (item) => {
    if (item.type === "empty") {
      return <EmptyWidgetSelector onSelect={(type) => changeWidgetType(item.i, type)} />;
    }
    if (item.type === "price_chart") return "📈 Price Chart Logic Here";
    if (item.type === "news_feed") return "📰 News Feed Logic Here";
    if (item.type === "financials") return "💰 Financial Data Here";
    return "Unknown Widget";
  };

  return (
    <div className="dashboard-container">
      <Link to="/profile" className="profile-icon">
        P
      </Link>
      {/* FLOATING ACTION BUTTON */}
      {/* Remove the "+" text inside, let CSS handle it */}
      <button onClick={addItem} className="add-btn"></button>

      <ResponsiveGrid
        className="layout"
        layouts={{ lg: items, md: items, sm: items, xs: items, xxs: items }}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={30}
        draggableHandle=".widget-header"
        onLayoutChange={onLayoutChange}
        margin={[10, 10]}
      >
        {items.map((item) => (
          <div key={item.i} className="dashboard-widget">
            <div className="widget-header">
              <span className="widget-title">
                {item.type === "empty" ? "NEW WIDGET" : item.type.toUpperCase().replace("_", " ")}
              </span>

              <button
                className="menu-btn"
                onMouseDown={(e) => e.stopPropagation()}
                onClick={(e) => toggleMenu(e, item.i)}
              >
                •••
              </button>

              {openMenuId === item.i && (
                <div className="dropdown-menu" onMouseDown={(e) => e.stopPropagation()}>
                  <div className="dropdown-item">⚙️ Settings</div>
                  <div className="dropdown-item delete-option" onClick={() => removeItem(item.i)}>
                    🗑️ Delete Widget
                  </div>
                </div>
              )}
            </div>

            <div className="widget-content">
              {renderWidgetContent(item)}
            </div>
          </div>
        ))}
      </ResponsiveGrid>
    </div>
  );
};

export default Dashboard;
