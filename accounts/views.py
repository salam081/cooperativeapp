from django.shortcuts import render,redirect,get_object_or_404
from django_countries import countries
from django.contrib import messages
from.models import *

from django.contrib.auth.models import User
from django.db.models import QuerySet
import pandas as pd
from decimal import Decimal
from django.shortcuts import render, redirect
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.shortcuts import redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from datetime import datetime
from accounts.models import Address, NextOfKin 
from accounts.models import User, Member, Gender

import os



def member_check(request):
    if request.method == 'POST':
        ippis = request.POST.get("ippis")
        if Member.objects.filter(ippis=ippis).exists():
            messages.error(request, "This  code is already taken.")
            return redirect("member_check")
        else:
            messages.success(request, f" member with, code {ippis} have Not being Taking")

            return redirect("register")

    return render(request,'accounts/member_check.html')


@login_required
def upload_users(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]
        relative_path = default_storage.save(f"upload/{excel_file.name}", ContentFile(excel_file.read()))
        absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        try:
            df = pd.read_excel(absolute_path, engine="openpyxl")

            if df.empty:
                messages.error(request, "The uploaded file is empty.")
                return redirect("upload_users")

            required_columns = [
                "username", "first_name", "last_name", "other_name",
                "date_of_birth", "department", "unit",
                "member_number", "ippis","gender","group","religion"
            ]
            for col in required_columns:
                if col not in df.columns:
                    messages.error(request, f"Missing column: {col}")
                    return redirect("upload_users")

            added, skipped = 0, 0

            for _, row in df.iterrows():
                try:
                    username = str(row["username"]).strip()
                    ippis = int(row["ippis"])
                    member_number = str(row["member_number"]).strip()

                    if User.objects.filter(username=username).exists() or Member.objects.filter(ippis=ippis).exists():
                        skipped += 1
                        continue
                     # Get foreign key values
                    gender = Gender.objects.filter(id=int(row["gender"])).first()
                    group = UserGroup.objects.filter(id=int(row["group"])).first()
                    religion = Religion.objects.filter(id=int(row["religion"])).first()

                    if not all([gender,group,religion, ]):#group, religion
                        skipped += 1
                        continue

                    user = User.objects.create(
                        username=username,
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        other_name=row.get("other_name", ""),
                        department=row["department"],
                        unit=row["unit"],
                        member_number=row["member_number"],
                        date_of_birth=row["date_of_birth"],
                        gender=gender,
                        group=group,
                        religion=religion
                    )
                    user.set_password('pass')
                    user.save()
                    Member.objects.create(
                        member=user,
                        ippis=ippis
                    )

                    added += 1

                except Exception as e:
                    skipped += 1
                    print(f"Row skipped due to error: {e}")

            messages.success(request, f"{added} users added, {skipped} skipped (duplicates or errors).")
            return redirect("upload_users")

        except Exception as e:
            messages.error(request, f"Error processing file: {e}")
            return redirect("upload_users")

    return render(request, "accounts/upload_users.html")



def user_registration(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        other_name = request.POST.get("other_name")
        username = request.POST.get("username", "").strip().lower()
        date_of_birth = request.POST.get("date_of_birth")
        department = request.POST.get("department")
        unit = request.POST.get("unit")
        gender_id = request.POST.get("gender") 
        passport = request.FILES.get("passport") 
        ippis = request.POST.get("ippis")
        member_number = request.POST.get("member_number")

        if Member.objects.filter(ippis=ippis).exists():
            messages.error(request, "This student code is already taken.")
            return redirect("register")

        try:
            user_group = UserGroup.objects.get(title='members')
        except UserGroup.DoesNotExist:
            messages.error(request, "User group 'members' not found.")
            return redirect("register")

        # If Gender is a ForeignKey:
        gender_instance = Gender.objects.get(id=gender_id) if gender_id else None

        user = User.objects.create(
            first_name=first_name,
            last_name=last_name,
            other_name=other_name,
            username=username,
            date_of_birth=date_of_birth,
            department=department,
            member_number=member_number,
            unit=unit,
            group=user_group,
            is_active=True,
            passport=passport, 
            gender=gender_instance  
        )

        user.set_password("pass")
        user.save()

        Member.objects.create(
            member=user,
            ippis=ippis,
            total_savings=0
        )

        messages.success(request, "Registration successful! Default password is 'pass1234'.")
        return redirect("create_or_update_address", id=user.id)

    genders = Gender.objects.all()  
    return render(request, "accounts/user_register.html", {"genders": genders})




def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password")
        default_password = "pass"

        try:
            user = User.objects.get(username=username)
            if user.is_active and not user.has_usable_password():
                user.set_password(default_password)
                user.save()
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("login")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back {user.username}')

            # === Check Member info ===
            if hasattr(user, "member"):
                member = user.member
                has_address = Address.objects.filter(user=member).exists()
                has_kin = NextOfKin.objects.filter(user=member).exists()

                if not has_address:
                    messages.info(request,'Update You Information ')
                    return redirect("create_or_update_address", id=member.id)
                elif not has_kin:
                    messages.info(request,'Update You Information ')
                    return redirect("create_or_update_next_of_kin", id=member.id)

            # === Redirect based on group ===
            if user.group and user.group.title.lower() == 'admin':
                return redirect('admin_dashboard')
            elif user.group and user.group.title.lower() == 'members':
                return redirect('member_dashboard')
            elif user.group and user.group.title.lower() == 'staff':
                return redirect('admin_dashboard')
            else:
                return redirect('login')
        else:
            messages.error(request, 'Invalid username or password')
            return redirect('login')

    return render(request, 'accounts/login.html')




def logout_view(request):
    logout(request) 
    messages.success(request, "You have been logged out.")
    return redirect('login')

def create_or_update_address(request, id):
    member = get_object_or_404(Member, pk=id)
    address, created = Address.objects.get_or_create(user=member)
    
    if request.method == "POST":
        address.phone1 = request.POST.get("phone1")
        address.phone2 = request.POST.get("phone2")
        address.email = request.POST.get("email")
        address.country = request.POST.get("country")
        address.state_of_origin_id = request.POST.get("state_of_origin")
        address.local_government_area = request.POST.get("local_government_area")
        address.address = request.POST.get("address")
        address.save()
        messages.success(request, "Address saved successfully!")
        return redirect("create_or_update_next_of_kin", id=member.id)

    states = State.objects.all()
    return render(request, "accounts/address_form.html", {"address": address, "states": states, "countries": list(countries) })



def create_or_update_next_of_kin(request, id):
    member = get_object_or_404(Member, pk=id)
    kin, created = NextOfKin.objects.get_or_create(user=member)

    if request.method == "POST":
        kin.full_names = request.POST.get("full_names")
        kin.phone_no = request.POST.get("phone_no")
        kin.address = request.POST.get("address")
        kin.email = request.POST.get("email")
        kin.save()
        messages.success(request, "Next of Kin saved successfully!")
        return redirect("member_detail", id=member.id)

    return render(request, "accounts/next_of_kin_form.html", {"kin": kin})

def all_members(request):
    members = User.objects.all()
    return render(request, "accounts/all_members.html", {"members": members})

def member_detail(request, id):
    member = get_object_or_404(Member, id=id)
    address = getattr(member, 'address', None)
    next_of_kin = getattr(member, 'nextofkin', None)

    context = {"member": member, "address": address, "next_of_kin": next_of_kin}
    return render(request, "accounts/member_detail.html", context)

@login_required
def deactivate_users(request):
    if request.method == 'POST':
        user_ids = request.POST.getlist('user_ids')
        if user_ids:
            users_to_deactivate: QuerySet[User] = User.objects.filter(id__in=user_ids)
            updated_count = users_to_deactivate.update(is_active=False)
            messages.success(request, f"{updated_count} user(s) have been deactivated.")
        else:
            messages.warning(request, "No users were selected for deactivation.")
        return redirect('all_members')
    return redirect('all_members')


@login_required
def activate_users(request):
    if request.method == 'POST':
        user_ids = request.POST.getlist('user_ids')

        # If form was submitted via JavaScript into one input (comma-separated)
        if len(user_ids) == 1 and ',' in user_ids[0]:
            user_ids = user_ids[0].split(',')

        # Filter out empty strings and convert to integers
        user_ids = [int(uid) for uid in user_ids if uid.strip().isdigit()]

        if user_ids:
            users_to_activate = User.objects.filter(id__in=user_ids)
            updated_count = users_to_activate.update(is_active=True)
            messages.success(request, f"{updated_count} user(s) have been activated.")
        else:
            messages.warning(request, "No valid users were selected for activation.")

        return redirect('all_members')

    return redirect('all_members')


def changePassword(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        if not request.user.check_password(old_password):
            messages.error(request, 'Old password is incorrect')
            return redirect('change_password')
        elif new_password1 != new_password2:
            messages.error(request, 'New passwords do not match')
            return redirect('change_password')
        else:
            request.user.set_password(new_password1)
            request.user.save()
            messages.success(request, 'Password successfully changed login ')
            return redirect('login')

    return render(request, 'accounts/change_password.html')



@login_required
def resetPassword(request,id):
    user = User.objects.get(id=id)
    user.set_password("pass")
    user.save()
    # PasswordResetLog.objects.create(reset_by=request.user,reset_for=user)

    messages.success(request, "Password reset successful!")
    return redirect('all_members')

