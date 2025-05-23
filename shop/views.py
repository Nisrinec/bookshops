from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.db.models import Q

from .models import Category, Product, Myrating
from django.contrib import messages
from cart.forms import CartAddProductForm
from surprise import Dataset, Reader, SVD
from surprise.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import pandas as pd


# for recommendation
def recommend(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_active:
        raise Http404

    ratings = Myrating.objects.all()
    products = Product.objects.all()

    data = []

    for rating in ratings:
        rating_data = {
            'user_id': rating.user_id,
            'product_id': rating.product_id,
            'rating': rating.rating,
        }
        data.append(rating_data)

    df = pd.DataFrame(data)

   
    df['author'] = df['product_id'].apply(lambda x: Product.objects.get(id=x).author)
    df['publisher'] = df['product_id'].apply(lambda x: Product.objects.get(id=x).publisher)

    
    author_encoder = LabelEncoder()
    publisher_encoder = LabelEncoder()
    df['author_code'] = author_encoder.fit_transform(df['author'])
    df['publisher_code'] = publisher_encoder.fit_transform(df['publisher'])

    reader = Reader(rating_scale=(1, 5))

    data = Dataset.load_from_df(df[['user_id', 'product_id', 'rating']], reader)

    trainset, testset = train_test_split(data, test_size=0.2)

    model = SVD()

    model.fit(trainset)

    current_user_id = request.user.id

    all_products = [product.id for product in products]

    unrated_products = [product for product in all_products if product not in df[df['user_id'] == current_user_id]['product_id'].values]

    recommendations = []
    for product_id in unrated_products:
        predicted_rating = model.predict(current_user_id, product_id).est
        author = Product.objects.get(id=product_id).author
        publisher = Product.objects.get(id=product_id).publisher
        recommendations.append({
            'product_id': product_id,
            'predicted_rating': predicted_rating,
            'author': author,
            'publisher': publisher,
        })

    recommendations_df = pd.DataFrame(recommendations)

    if not recommendations_df.empty:
        recommendations_df = recommendations_df.sort_values('predicted_rating', ascending=False)
        product_list = []
        for index, row in recommendations_df.iterrows():
            product_id = row['product_id']
            predicted_rating = row['predicted_rating']
            product = Product.objects.get(id=product_id)
            product_dict = {
                'get_absolute_url': product.get_absolute_url,
                'image': product.image,
                'name': product.name,
                'category': product.category,
                'price': product.price,
                'stock': product.stock,
                'predicted_rating': predicted_rating,
            }
            product_list.append(product_dict)
        product_list = product_list[:1]
        return render(request, 'shop/recommend.html', {'product_list': product_list})
    else:
        message = "You have rated all the available books. At the moment, we have no more recommendations for you."
        return render(request, 'shop/recommend.html', {'message': message})


# List
def product_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    search_term = ''
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=category)

    if 'search' in request.GET:
        search_term = request.GET['search']
        if search_term:
            products = Product.objects.filter(name__icontains=search_term)
            if products:
                messages.success(request, 'Results found for the query: ' + search_term)
            else:
                messages.success(request, 'Nothing was found :(')
        else:
            messages.warning(request, 'Your query is empty')

    query = request.GET.get('q')
    if query:
        products = Product.objects.filter(Q(title__icontains=query)).distinct()
        return render(request, 'shop/list.html', {'products': products})

    context = {
        'category': category,
        'categories': categories,
        'products': products,
        'search_term': search_term
    }
    return render(request, 'shop/list.html', context)


# detail
def product_detail(request, id, slug):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_active:
        raise Http404
    product = get_object_or_404(Product, id=id, slug=slug, available=True)

    cart_product_form = CartAddProductForm()

    # rating
    if request.method == "POST":
        rate = request.POST['rating']

        
        existing_rating = Myrating.objects.filter(user=request.user, product=product).first()
        if existing_rating:
            messages.error(request, "You have already rated this book.")
        else:
            ratingObject = Myrating()
            ratingObject.user = request.user
            ratingObject.product = product
            ratingObject.rating = rate
            ratingObject.save()
            messages.success(request, "Your review has been added ")

        return redirect('shop:product_list')

    rating = Myrating.objects.filter(user=request.user, product=product).first()
    context = {
        'product': product,
        'cart_product_form': cart_product_form,
        'rated': rating is not None,
        'rating': rating.rating if rating else 0,
    }

    return render(request, 'shop/detail.html', context)


    context = {
        'product': product,
        'cart_product_form': cart_product_form,
    }

    return render(request, 'shop/detail.html', context)
