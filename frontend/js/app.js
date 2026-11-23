const TOKEN_KEY = "amiperfumehub_token";
const token = () => localStorage.getItem(TOKEN_KEY);
const money = value => new Intl.NumberFormat("en-NG", {style:"currency",currency:"NGN"}).format(Number(value || 0));
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const imageUrl = value => { if(!value)return "/static/assets/perfume-placeholder.svg";try { const url = new URL(value, location.origin); return url.origin===location.origin||url.protocol==="https:" ? url.href : "/static/assets/perfume-placeholder.svg"; } catch { return "/static/assets/perfume-placeholder.svg"; } };

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token()) headers.set("Authorization", `Bearer ${token()}`);
  const response = await fetch(path, {...options, headers});
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.detail || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function notice(message, kind = "success") {
  const box = document.querySelector("[data-notice]");
  if (!box) return;
  box.textContent = message;
  box.className = `notice ${kind}`;
  box.hidden = false;
}
function errorNotice(error) { notice(error.message || "Something went wrong. Please try again.", "error"); }
function productCard(product) {
  return `<article class="product-card"><a href="/static/product.html?id=${product.id}"><img src="${esc(imageUrl(product.image_url))}" alt="${esc(product.name)}" loading="lazy"></a><div class="product-card-body"><span class="eyebrow">${esc(product.category)}</span><h3><a href="/static/product.html?id=${product.id}">${esc(product.name)}</a></h3><span class="muted small">By ${esc(product.vendor?.business_name || product.vendor?.full_name || "Marketplace vendor")}</span><span class="price">${money(product.price)}</span><a class="button" href="/static/product.html?id=${product.id}">View fragrance</a></div></article>`;
}
function statusPill(value) { return `<span class="status-pill">${esc(value)}</span>`; }
async function uploadImage(button) {
  const group=button.closest(".image-upload"); const file=group.querySelector('input[type="file"]').files[0];
  if(!file)return notice("Choose an image file first.","error");
  const form=new FormData(); form.append("file",file);
  try { const result=await api("/products/images",{method:"POST",body:form}); group.querySelector('[name="image_url"]').value=result.image_url; notice("Image uploaded."); }
  catch(error){errorNotice(error);}
}

async function setupHeader() {
  const root = document.querySelector("#site-header");
  if (!root) return;
  let user = null;
  if (token()) {
    try { user = await api("/auth/me"); }
    catch { localStorage.removeItem(TOKEN_KEY); }
  }
  const dashboard = user?.role === "admin" ? '<a href="/static/admin/dashboard.html">Admin</a>' : user?.role === "vendor" ? '<a href="/static/vendor/dashboard.html">Vendor</a>' : user ? '<a href="/static/profile.html">Account</a><a href="/static/orders.html">My orders</a><a href="/static/vendor-apply.html">Sell with us</a>' : '<a href="/static/vendor-apply.html">Sell with us</a><a href="/static/admin/login.html">Admin sign in</a>';
  root.innerHTML = `<header class="site-header"><nav class="nav"><a class="brand" href="/"><span>AMÍ</span> PerfumeHub</a><button class="menu-toggle" aria-label="Toggle navigation">☰</button><div class="nav-links"><a href="/static/products.html">Shop</a><a href="/static/products.html?category=Floral">Floral</a>${dashboard}<a href="/static/cart.html">Cart</a>${user ? '<a href="#" data-logout>Log out</a>' : '<a href="/static/login.html">Log in</a><a class="button" href="/static/register.html">Create account</a>'}</div></nav></header>`;
  root.querySelector(".menu-toggle").addEventListener("click", () => root.querySelector(".nav-links").classList.toggle("open"));
  root.querySelector("[data-logout]")?.addEventListener("click", event => { event.preventDefault(); localStorage.removeItem(TOKEN_KEY); location.href = "/"; });
}
function footer() {
  const root = document.querySelector("#site-footer");
  if (root) root.innerHTML = '<footer class="footer"><div class="footer-inner"><span class="brand"><span>AMÍ</span> PerfumeHub</span><small>Discover your signature scent. Payment on delivery across our marketplace.</small><small>© AMIPerfumeHub</small></div></footer>';
}
async function requireRole(roles) {
  if (!token()) { location.href = "/static/login.html"; throw new Error("Please log in to continue."); }
  const user = await api("/auth/me");
  if (!roles.includes(user.role)) { location.href = user.role === "vendor" ? "/static/vendor/dashboard.html" : user.role === "admin" ? "/static/admin/dashboard.html" : "/"; throw new Error("This page is not available for your account."); }
  return user;
}
function queryString(form) { return new URLSearchParams(new FormData(form)).toString(); }

async function homePage() {
  const products = await api("/products?limit=4");
  document.querySelector("#featured").innerHTML = products.length ? products.map(productCard).join("") : '<div class="empty">New fragrances are coming soon.</div>';
}
async function productsPage() {
  const form = document.querySelector("#filters");
  const initial = new URLSearchParams(location.search);
  let offset = 0;
  for (const field of ["q","category","vendor_id","min_price","max_price"]) if (initial.has(field)) form.elements[field].value = initial.get(field);
  const load = async () => {
    const params = new URLSearchParams(new FormData(form));
    params.set("limit", "40");
    params.set("offset", String(offset));
    for (const [key,value] of [...params]) if (!value) params.delete(key);
    const products = await api(`/products?${params}`);
    document.querySelector("#results").innerHTML = products.length ? products.map(productCard).join("") : '<div class="empty">No fragrances match those filters.</div>';
    document.querySelector("#page-count").textContent = products.length ? `Showing ${offset + 1}–${offset + products.length}` : "";
    document.querySelector("#previous-page").disabled = offset === 0;
    document.querySelector("#next-page").disabled = products.length < 40;
  };
  form.addEventListener("submit", event => { event.preventDefault(); offset = 0; load().catch(errorNotice); });
  document.querySelector("#previous-page").addEventListener("click",()=>{offset=Math.max(0,offset-40);load().catch(errorNotice);});
  document.querySelector("#next-page").addEventListener("click",()=>{offset+=40;load().catch(errorNotice);});
  await load();
}
async function productPage() {
  const id = new URLSearchParams(location.search).get("id");
  const product = await api(`/products/${encodeURIComponent(id)}`);
  document.querySelector("#product-detail").innerHTML = `<div><img src="${esc(imageUrl(product.image_url))}" alt="${esc(product.name)}"></div><div><span class="eyebrow">${esc(product.category)}</span><h1>${esc(product.name)}</h1><p class="muted">${esc(product.description || "A considered fragrance, selected by our marketplace vendors.")}</p><p class="muted">Sold by ${esc(product.vendor?.business_name || product.vendor?.full_name || "Marketplace vendor")}</p><h2>${money(product.price)}</h2><p class="muted">${product.stock} in stock</p><form id="add-cart" class="form-grid"><label>Quantity<input type="number" name="quantity" value="1" min="1" max="${product.stock}" required></label><button>Add to cart</button></form><div class="notice" data-notice hidden></div></div>`;
  document.querySelector("#add-cart").addEventListener("submit", async event => { event.preventDefault(); try { if (!token()) { location.href = "/static/login.html"; return; } await api("/cart/items", {method:"POST",body:JSON.stringify({product_id:product.id,quantity:Number(new FormData(event.currentTarget).get("quantity"))})}); notice("Added to your cart."); } catch(error) { errorNotice(error); } });
}
async function loginPage() {
  const form=document.querySelector("#login-form");
  const submit=form.querySelector("[type=submit]");
  const statusLine=document.querySelector("#login-status");
  const adminLogin=document.body.dataset.page==="adminLogin";
  form.addEventListener("submit", async event => {
    event.preventDefault(); const body = Object.fromEntries(new FormData(form));
    const previousNotice=document.querySelector("[data-notice]");
    if(previousNotice) previousNotice.hidden=true;
    submit.disabled=true;
    submit.setAttribute("aria-busy","true");
    submit.textContent="Signing in…";
    statusLine.className="notice info";
    statusLine.textContent="Checking your email and password…";
    statusLine.hidden=false;
    try {
      const result = await api("/auth/login", {method:"POST",body:JSON.stringify(body)});
      localStorage.setItem(TOKEN_KEY,result.access_token);
      const user = await api("/auth/me");
      if(adminLogin && user.role!=="admin") { localStorage.removeItem(TOKEN_KEY); throw new Error("This account does not have administrator access."); }
      statusLine.className="notice success";
      statusLine.textContent="Sign-in successful. Opening your dashboard…";
      await new Promise(resolve=>setTimeout(resolve,650));
      location.href = user.role === "admin" ? "/static/admin/dashboard.html" : user.role === "vendor" ? "/static/vendor/dashboard.html" : "/static/products.html";
    }
    catch(error) {
      localStorage.removeItem(TOKEN_KEY);
      statusLine.className="notice error";
      if(error.status===401) statusLine.textContent="Email or password is incorrect. Please try again.";
      else if(error instanceof TypeError) statusLine.textContent="Could not reach the server. Check that AMIPerfumeHub is running and try again.";
      else statusLine.textContent=error.message || "Sign-in failed. Please try again.";
    }
    finally {
      submit.disabled=false;
      submit.removeAttribute("aria-busy");
      submit.textContent=adminLogin?"Admin sign in":"Log in";
    }
  });
}
async function registerPage() {
  document.querySelector("#register-form").addEventListener("submit", async event => {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget));
    if (data.password !== data.confirm_password) return notice("Passwords do not match.", "error");
    delete data.confirm_password;
    try { await api("/auth/register", {method:"POST",body:JSON.stringify(data)}); notice("Account created. You can now log in."); event.currentTarget.reset(); }
    catch(error) { errorNotice(error); }
  });
}
async function vendorApplyPage() {
  const user = await requireRole(["customer"]);
  document.querySelector("#applicant-name").textContent = user.full_name;
  try { const application = await api("/auth/vendor-register"); document.querySelector("#application-state").innerHTML = `<p>Your application for <strong>${esc(application.business_name)}</strong> is ${statusPill(application.status)}.</p>${application.review_note ? `<p class="muted">Review note: ${esc(application.review_note)}</p>` : ""}`; if(application.status!=="rejected") document.querySelector("#vendor-apply-form").hidden=true; }
  catch(error) { if (!String(error.message).includes("No vendor application")) errorNotice(error); }
  document.querySelector("#vendor-apply-form").addEventListener("submit", async event => { event.preventDefault(); try { const result = await api("/auth/vendor-register",{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(event.currentTarget)))}); document.querySelector("#application-state").innerHTML=`<p>Application submitted for <strong>${esc(result.business_name)}</strong>. Status: ${statusPill(result.status)}.</p>`; event.currentTarget.reset(); event.currentTarget.hidden=true; } catch(error) { errorNotice(error); } });
}
function cartLine(item) { return `<div class="cart-line"><img src="${esc(imageUrl(item.image_url))}" alt=""><div><strong>${esc(item.product_name)}</strong><p class="muted small">${money(item.unit_price)} each · ${item.available_stock} in stock ${item.is_available ? "" : "· currently unavailable"}</p></div><input aria-label="Quantity" type="number" min="1" max="${item.available_stock}" value="${item.quantity}" data-quantity="${item.id}"><button class="danger remove" data-remove="${item.id}">Remove</button><strong>${money(item.subtotal)}</strong></div>`; }
async function cartPage() {
  const render = async () => { const cart = await api("/cart"); document.querySelector("#cart-lines").innerHTML = cart.items.length ? cart.items.map(cartLine).join("") : '<div class="empty">Your cart is empty. <a href="/static/products.html">Explore the collection.</a></div>'; document.querySelector("#cart-total").textContent = money(cart.total); document.querySelector("#checkout-link").hidden = !cart.items.length; document.querySelectorAll("[data-remove]").forEach(button => button.addEventListener("click", async () => { try { await api(`/cart/items/${button.dataset.remove}`,{method:"DELETE"}); await render(); } catch(error) { errorNotice(error); } })); document.querySelectorAll("[data-quantity]").forEach(input => input.addEventListener("change", async () => { try { const result = await api(`/cart/items/${input.dataset.quantity}`,{method:"PUT",body:JSON.stringify({quantity:Number(input.value)})}); document.querySelector("#cart-total").textContent=money(result.total); await render(); } catch(error) { errorNotice(error); } })); };
  await requireRole(["customer"]); await render();
}
async function checkoutPage() {
  await requireRole(["customer"]); const cart = await api("/cart");
  document.querySelector("#checkout-summary").innerHTML = cart.items.length ? `${cart.items.map(item=>`<p>${esc(item.product_name)} × ${item.quantity} <strong>${money(item.subtotal)}</strong></p>`).join("")}<hr><h3>Total: ${money(cart.total)}</h3>` : '<div class="empty">Your cart is empty.</div>';
  const form=document.querySelector("#checkout-form"); form.addEventListener("submit", async event=>{event.preventDefault();try{const order=await api("/orders",{method:"POST",body:JSON.stringify({delivery_address:new FormData(form).get("delivery_address"),payment_method:"cash_on_delivery"})});notice(`Order ${order.order_number} placed.`);setTimeout(()=>location.href="/static/orders.html",900);}catch(error){errorNotice(error);}});
}
async function ordersPage() {
  await requireRole(["customer"]); const orders=await api("/orders");
  document.querySelector("#orders-list").innerHTML=orders.length?orders.map(order=>`<article class="panel space-top"><div class="section-heading"><div><span class="eyebrow">${esc(order.order_number)}</span><p class="muted small">${new Date(order.created_at).toLocaleString()}</p></div><div>${statusPill(order.status)} <strong>${money(order.total_amount)}</strong></div></div>${order.items.map(item=>`<p>${esc(item.product_name)} × ${item.quantity} — ${money(item.subtotal)} ${statusPill(item.status)}</p>`).join("")}<p class="muted">${esc(order.delivery_address)} · Payment on delivery (${esc(order.payment_status)})</p></article>`).join(""):'<div class="empty">You have not placed an order yet.</div>';
}
async function profilePage() {
  const user=await api("/auth/me");
  document.querySelector("#profile-name").value=user.full_name;
  document.querySelector("#profile-email").textContent=user.email;
  document.querySelector("#profile-form").addEventListener("submit",async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget));for(const key of Object.keys(data))if(!data[key])delete data[key];try{await api("/auth/me",{method:"PATCH",body:JSON.stringify(data)});notice("Account details updated.");}catch(error){errorNotice(error);}});
}
function productEditor(product) { return `<tr data-product-row="${product.id}"><td>${esc(product.name)}</td><td><input name="name" value="${esc(product.name)}"></td><td><input name="category" value="${esc(product.category)}"></td><td><input name="price" type="number" step="0.01" min="0.01" value="${product.price}"></td><td><input name="stock" type="number" min="0" value="${product.stock}"></td><td><div class="image-upload"><input name="image_url" value="${esc(product.image_url||"")}" placeholder="Image URL"><input type="file" accept="image/png,image/jpeg,image/webp,image/gif"><button class="secondary" type="button" data-upload-image>Upload image</button></div><input name="description" value="${esc(product.description||"")}" placeholder="Description"></td><td><input name="is_available" type="checkbox" ${product.is_available?"checked":""}></td><td><button data-save-product="${product.id}">Save</button> <button class="danger" data-disable-product="${product.id}">Deactivate</button></td></tr>`; }
async function vendorPage() {
  const user=await requireRole(["vendor"]); document.querySelector("#vendor-welcome").textContent=user.full_name;
  const [stats,products,orders]=await Promise.all([api("/vendor/dashboard"),api("/products/mine?limit=100"),api("/orders/vendor?limit=100")]);
  const profile=await api("/vendor/profile");
  const profileForm=document.querySelector("#vendor-profile-form");
  for(const field of ["business_name","business_description","contact_phone"])profileForm.elements[field].value=profile[field]||"";
  profileForm.addEventListener("submit",async event=>{event.preventDefault();try{await api("/vendor/profile",{method:"PUT",body:JSON.stringify(Object.fromEntries(new FormData(profileForm)))});notice("Business profile updated.");}catch(error){errorNotice(error);}});
  document.querySelector("#vendor-stats").innerHTML=[["Products",stats.total_products],["Available",stats.available_products],["Out of stock",stats.out_of_stock_products],["Incoming orders",stats.incoming_orders],["Delivered sales",money(stats.delivered_sales)]].map(([name,value])=>`<div class="stat"><span class="muted">${name}</span><strong>${value}</strong></div>`).join("");
  document.querySelector("#vendor-products").innerHTML=products.length?`<div class="table-wrap"><table><thead><tr><th>Current listing</th><th>Name</th><th>Category</th><th>Price (₦)</th><th>Stock</th><th>Image and description</th><th>Available</th><th>Actions</th></tr></thead><tbody>${products.map(productEditor).join("")}</tbody></table></div>`:'<div class="empty">You have not listed products yet.</div>';
  document.querySelectorAll("[data-save-product]").forEach(button=>button.addEventListener("click",async()=>{const row=button.closest("tr"),data={};for(const name of ["name","category","price","stock","image_url","description"])data[name]=row.querySelector(`[name=${name}]`).value;data.price=Number(data.price);data.stock=Number(data.stock);data.is_available=row.querySelector("[name=is_available]").checked;try{await api(`/products/${button.dataset.saveProduct}`,{method:"PUT",body:JSON.stringify(data)});notice("Product updated.");}catch(error){errorNotice(error);}}));
  document.querySelectorAll("[data-disable-product]").forEach(button=>button.addEventListener("click",async()=>{try{await api(`/products/${button.dataset.disableProduct}`,{method:"DELETE"});button.closest("tr").remove();notice("Product deactivated.");}catch(error){errorNotice(error);}}));
  document.querySelectorAll("[data-upload-image]").forEach(button=>button.addEventListener("click",()=>uploadImage(button)));
  document.querySelector("#new-product-form").addEventListener("submit",async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget));data.price=Number(data.price);data.stock=Number(data.stock);data.is_available=true;try{await api("/products",{method:"POST",body:JSON.stringify(data)});location.reload();}catch(error){errorNotice(error);}});
  const nextItemStatuses={pending:["confirmed","cancelled"],confirmed:["processing","cancelled"],processing:["shipped","cancelled"],shipped:["delivered"],delivered:[],cancelled:[]};
  document.querySelector("#vendor-orders").innerHTML=orders.length?orders.map(order=>`<article class="panel space-top"><div class="section-heading"><div><span class="eyebrow">${esc(order.order_number)}</span><p>${esc(order.customer_name)} · ${esc(order.delivery_address)}</p></div>${statusPill(order.order_status)}</div>${order.items.map(item=>`<div class="toolbar"><span>${esc(item.product_name)} × ${item.quantity}</span>${statusPill(item.status)}<select data-item-status="${item.id}" data-order-id="${order.order_id}"><option value="">Update status</option>${(nextItemStatuses[item.status]||[]).map(value=>`<option value="${value}">${value}</option>`).join("")}</select></div>`).join("")}</article>`).join(""):'<div class="empty">No orders for your products yet.</div>';
  document.querySelectorAll("[data-item-status]").forEach(select=>select.addEventListener("change",async()=>{if(!select.value)return;try{await api(`/orders/${select.dataset.orderId}/items/${select.dataset.itemStatus}/status`,{method:"PATCH",body:JSON.stringify({status:select.value})});location.reload();}catch(error){errorNotice(error);}}));
}
async function adminPage() {
  await requireRole(["admin"]); const [stats,applications,users,products,orders]=await Promise.all([api("/admin/dashboard"),api("/admin/vendors/applications?status=pending"),api("/admin/users?limit=100"),api("/admin/products?limit=100"),api("/admin/orders?limit=100")]);
  document.querySelector("#admin-stats").innerHTML=[["Customers",stats.total_customers],["Vendors",stats.total_vendors],["Vendor applications",stats.pending_vendor_applications],["Products",stats.total_products],["Orders",stats.total_orders]].map(([name,value])=>`<div class="stat"><span class="muted">${name}</span><strong>${value}</strong></div>`).join("");
  document.querySelector("#applications").innerHTML=applications.length?applications.map(app=>`<article class="panel space-top"><h3>${esc(app.business_name)}</h3><p>${esc(app.user.full_name)} · ${esc(app.user.email)}</p><p class="muted">${esc(app.business_description||"")} ${esc(app.contact_phone||"")}</p><div class="row-actions"><button data-approve="${app.id}">Approve</button><button class="danger" data-reject="${app.id}">Reject</button></div></article>`).join(""):'<div class="empty">No pending applications.</div>';
  for(const action of ["approve","reject"])document.querySelectorAll(`[data-${action}]`).forEach(button=>button.addEventListener("click",async()=>{try{await api(`/admin/vendors/${button.dataset[action]}/${action}`,{method:"PATCH",body:JSON.stringify({review_note:""})});location.reload();}catch(error){errorNotice(error);}}));
  document.querySelector("#users").innerHTML=`<div class="table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Active</th><th>Action</th></tr></thead><tbody>${users.map(user=>`<tr><td>${esc(user.full_name)}</td><td>${esc(user.email)}</td><td>${esc(user.role)}</td><td>${user.is_active?"Yes":"No"}</td><td><button data-user-status="${user.id}" data-active="${user.is_active}">${user.is_active?"Suspend":"Activate"}</button></td></tr>`).join("")}</tbody></table></div>`;
  document.querySelectorAll("[data-user-status]").forEach(button=>button.addEventListener("click",async()=>{try{await api(`/admin/users/${button.dataset.userStatus}/status`,{method:"PATCH",body:JSON.stringify({is_active:button.dataset.active!=="true"})});location.reload();}catch(error){errorNotice(error);}}));
  document.querySelector("#admin-products").innerHTML=`<div class="table-wrap"><table><thead><tr><th>Product</th><th>Vendor</th><th>Stock</th><th>Availability</th><th>Action</th></tr></thead><tbody>${products.map(product=>`<tr><td>${esc(product.name)}</td><td>${esc(product.vendor.full_name)}</td><td>${product.stock}</td><td>${product.is_available?"Available":"Hidden"}</td><td><button data-product-availability="${product.id}" data-available="${product.is_available}">${product.is_available?"Hide listing":"Show listing"}</button></td></tr>`).join("")}</tbody></table></div>`;
  document.querySelectorAll("[data-product-availability]").forEach(button=>button.addEventListener("click",async()=>{try{await api(`/admin/products/${button.dataset.productAvailability}/availability`,{method:"PATCH",body:JSON.stringify({is_available:button.dataset.available!=="true"})});location.reload();}catch(error){errorNotice(error);}}));
  const userById=new Map(users.map(user=>[user.id,user]));
  document.querySelector("#admin-orders").innerHTML=`<div class="table-wrap"><table><thead><tr><th>Reference and items</th><th>Customer</th><th>Total</th><th>Status</th><th>Payment</th><th>Actions</th></tr></thead><tbody>${orders.map(order=>`<tr><td><strong>${esc(order.order_number)}</strong><details><summary>View items</summary>${order.items.map(item=>`<p>${esc(item.product_name)} × ${item.quantity} (${esc(item.status)})</p>`).join("")}<small>${esc(order.delivery_address)}</small></details></td><td>${esc(userById.get(order.customer_id)?.full_name||order.customer_id)}</td><td>${money(order.total_amount)}</td><td><select data-order-status="${order.id}">${["pending","confirmed","processing","shipped","delivered","cancelled"].map(state=>`<option ${state===order.status?"selected":""} value="${state}">${state}</option>`).join("")}</select></td><td>${esc(order.payment_status)}</td><td><button data-paid="${order.id}">Mark paid</button></td></tr>`).join("")}</tbody></table></div>`;
  document.querySelectorAll("[data-order-status]").forEach(select=>select.addEventListener("change",async()=>{try{await api(`/admin/orders/${select.dataset.orderStatus}/status`,{method:"PATCH",body:JSON.stringify({status:select.value})});location.reload();}catch(error){errorNotice(error);}}));
  document.querySelectorAll("[data-paid]").forEach(button=>button.addEventListener("click",async()=>{try{await api(`/admin/orders/${button.dataset.paid}/payment`,{method:"PATCH",body:JSON.stringify({payment_status:"paid"})});location.reload();}catch(error){errorNotice(error);}}));
}

document.addEventListener("DOMContentLoaded",async()=>{
  await setupHeader(); footer();
  const page=document.body.dataset.page;
  document.querySelectorAll("[data-password-toggle]").forEach(button=>button.addEventListener("click",()=>{const input=document.getElementById(button.dataset.passwordToggle);input.type=input.type==="password"?"text":"password";button.textContent=input.type==="password"?"Show":"Hide";}));
  const actions={home:homePage,products:productsPage,product:productPage,login:loginPage,adminLogin:loginPage,register:registerPage,vendorApply:vendorApplyPage,cart:cartPage,checkout:checkoutPage,orders:ordersPage,profile:profilePage,vendor:vendorPage,admin:adminPage};
  try { if(actions[page]) await actions[page](); }
  catch(error) { if(error.message) errorNotice(error); }
});
