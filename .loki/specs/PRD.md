# PRD: 宝宝的私房菜馆

## 1. Project Overview
A lightweight, mobile-first web application for family members to order dishes and manage a shared dish library in 'Baby's Private Kitchen'.

## 2. Target Users
Family members who want to coordinate meals and record food preferences.

## 3. Core Features
### 3.1 Dish Management
- **Dish Library**: A persistent collection of dishes.
- **Self-Creation**: Users can add new dishes to the library.
- **Auto-Save**: Newly created dishes are automatically saved for future selection.
- **Editing**: Users can edit existing dish details.
- **Selection**: Users can pick dishes from the library for current orders.

### 3.2 Ordering System
- **Single/Multi-user Entry**: Any family member can initiate or contribute to a "session" or directly create an order.
- **Order Details**: Each ordered item includes:
    - Taste (口味)
    - Time (想吃的时间)
    - Location (想吃的地点)
    - Ingredients (原材料)
    - Remarks (备注)
    - Custom fields/Customizable input.
- **Order Summary**: A centralized view of all selected dishes and their details.

### 3.3 Visibility & Audit
- **Shared Access**: All users can view and edit the order page and selection page.
- **Audit Logging**: Record which user performed what action (e.g., "User A added Dish X", "User B changed Taste to Spicy").
- **History**: View past ordering records.

### 3.4 Image Management
- Ability to upload images for dishes (optional but requested to be simple).

## 4. UI/UX Requirements
- **Mobile First**: Optimized for phone web browsers.
- **Reference**: UI should follow the aesthetic and layout of `app.jpg`.
- **Lightweight**: Minimalist design, fast loading.

## 5. Technical Constraints
- **Backend**: Python 3.
- **Database**: PostgreSQL.
- **Deployment**: Simple and portable.
- **Audit**: Every mutation must be logged with a timestamp and user ID.

## 6. Success Criteria
- Functional end-to-end ordering flow.
- Audit trail correctly capturing changes.
- Responsive mobile UI.
