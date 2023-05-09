import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from esi.decorators import token_required
from allianceauth.srp.models import SrpFleetMain
from allianceauth.srp.models import SrpUserRequest
from .models import SrpPaymentToken

from django.db.models import Sum, F
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from allianceauth.srp.models import SrpUserRequest
import copy

logger = logging.getLogger(__name__)

from . import providers

@login_required
@permission_required('srp.access_srp')
def srp_fleet_view(request, fleet_id):
    logger.debug("srp_fleet_view called by user %s for fleet id %s" % (request.user, fleet_id))
    try:
        fleet_main = SrpFleetMain.objects.get(id=fleet_id)
    except SrpFleetMain.DoesNotExist:
        raise Http404
    context = {"fleet_id": fleet_id, "fleet_status": fleet_main.fleet_srp_status,
               "srpfleetrequests": fleet_main.srpuserrequest_set.select_related('character').order_by('srp_ship_name'),
               "totalcost": fleet_main.total_cost}

    return render(request, 'srpmod/data.html', context=context)


@login_required
@permission_required('auth.srp_management')
@token_required(['esi-ui.open_window.v1', 'esi-location.read_online.v1'])
def srp_set_payment_character(request, token, fleet_id=None):
    if token:
        srp_link = False
        try:
            srp_link = SrpPaymentToken.objects.get(user=request.user)
        except:
            pass
        if srp_link:
            srp_link.token = token
            srp_link.save()
        else:
            SrpPaymentToken.objects.create(user=request.user, token=token)
    messages.success(request,
                    _("Linked SRP Payments Character: {}".format(token.character_name)))
    if fleet_id:
        return redirect("srp:fleet", fleet_id)
    else:
        return redirect("srp:management")


@login_required
@permission_required('auth.srp_management')
def srp_open_info(request, id=None):
    try:
        if id:
            linked = request.user.srp_character
            if linked:
                logger.info("SRPMOD: {id} - checking {linked} online")
                online = providers.provider.client.Location.get_characters_character_id_online(character_id=linked.token.character_id, _request_options=providers.get_operation_auth_headers(linked.token)).result()
                if online.get('online', False):
                    logger.info("SRPMOD: {id} - {linked} is online")
                    resp = providers.provider.client.User_Interface.post_ui_openwindow_information(target_id=id, _request_options=providers.get_operation_auth_headers(linked.token)).result()
                    logger.info("SRPMOD: {id} - {linked} open window response {resp}")
                else:
                    logger.info("SRPMOD:{id} - {linked} is offline")
                    return HttpResponse("Failed! Character Offline!")
            else:
                return HttpResponse("Failed! No Linked Cahracter!")
        return HttpResponse("Success!")
    except:
        return HttpResponse("Failed!")


@login_required
@permission_required('srp.access_srp')
def srp_management(request, all=False):
    logger.debug("srp_management called by user %s" % request.user)
    fleets = SrpFleetMain.objects.select_related('fleet_commander').prefetch_related('srpuserrequest_set').all()

    now = timezone.now()
    dt = now - relativedelta(months=12)
    output_array={}
    fleet_breakout = SrpUserRequest.objects.select_related('srp_fleet_main')\
                            .filter(srp_fleet_main__fleet_time__gte=dt)\
                            .values('srp_fleet_main')\
                            .annotate(total_cost=Sum('srp_total_amount'))\
                            .annotate(fc_name=F('srp_fleet_main__fleet_commander__character_name'))\
                            .annotate(fleet_date=F('srp_fleet_main__fleet_time'))\
                            .order_by('-fleet_date')

    output_areay_scafold = {}
    global_srp = {}

    try:
        tempdate = fleet_breakout.filter().last().get('fleet_date')
        tempdate = tempdate.replace(day = 1).replace(hour = 0).replace(minute = 0)
        while tempdate < timezone.now():
            date_str = tempdate.strftime("%Y-%m")
            output_areay_scafold[date_str] = 0
            tempdate = tempdate + relativedelta(months=1)

        global_srp = copy.deepcopy(output_areay_scafold)

        for fleet in fleet_breakout:
            if fleet.get('fc_name') not in output_array:
                output_array[fleet.get('fc_name')] = copy.deepcopy(output_areay_scafold)
            try:
                date_str = fleet.get('fleet_date').strftime("%Y-%m")
                output_array[fleet.get('fc_name')][date_str] += fleet.get('total_cost')
                global_srp[date_str] += fleet.get('total_cost')
            except:
                pass
    except:
        pass
    if not all:
        fleets = fleets.filter(fleet_srp_status="")
    else:
        logger.debug("Returning all SRP requests")
    totalcost = fleets.aggregate(total_cost=Sum('srpuserrequest__srp_total_amount')).get('total_cost', 0)
    context = {"srpfleets": fleets, "totalcost": totalcost, 'graph':output_array,'graph_label':output_areay_scafold,'all_srp':global_srp}
    return render(request, 'srpmod/management.html', context=context)



