/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { loadJS, loadCSS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
import { useModelWithSampleData } from "@web/model/model";
import { standardViewProps } from "@web/views/standard_view_props";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useSearchBarToggler } from "@web/search/search_bar/search_bar_toggler";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import {formatDateTime, deserializeDateTime, serializeDate } from "@web/core/l10n/dates";
import { Component, onWillUnmount, onWillStart, useState } from "@odoo/owl";

const { DateTime } = luxon;

export class BaseGanttController extends Component {
    setup() {
        this.action = useService("action");
        this.dialog = useService('dialog');

        this.state = useState({
            timeFrame : 'Month',
        });

        const Model = this.props.Model;
        const model = useModelWithSampleData(Model, this.props.modelParams);
        this.model = model;

        onWillUnmount(() => {});

        useSetupAction({
            getLocalState: () => {
                return this.model.metaData;
            },
        });

        onWillStart(async () => {
            await loadJS("/kojto_base/static/src/lib/frappe-gantt.js");
            await loadJS("/kojto_base/static/src/lib/snap.svg-min.js");
            await loadJS("/kojto_base/static/src/lib/moment.min.js");
            await loadCSS("/kojto_base/static/src/lib/frappe-gantt.css");
        });

        this.searchBarToggler = useSearchBarToggler();
    }

    get rendererProps() {
        return {
            model: this.model,
        };
    }
    
    onNewTask(){
        var self = this;
        var context = {};
        var startDate = serializeDate(DateTime.now());
        var endDate;

        switch (self.model.metaData.timeFrame) {
            case "Quarter Day":
                endDate = serializeDate(DateTime.now().plus({ hours: 4 }));
                break;
            case "Half Day":
                endDate = serializeDate(DateTime.now().plus({ hours: 12 }));
                break;
            case "Day":
                endDate = serializeDate(DateTime.now().plus({ days: 1 }));
                break;
            case "Week":
                endDate = serializeDate(DateTime.now().plus({ weeks: 1 }));
                break;
            case "Month":
                endDate = serializeDate(DateTime.now().plus({ months: 1 }));
                break;
        }

        var start_date_formatted = formatDateTime(deserializeDateTime(startDate), {
            format: "yyyy-MM-dd HH:mm:ss",
            numberingSystem: "latn",
        })
        var end_date_formatted = formatDateTime(deserializeDateTime(endDate), {
            format: "yyyy-MM-dd HH:mm:ss",
            numberingSystem: "latn",
        })

        if (self.model.metaData?.dateStartField) {
            context[`default_${self.model.metaData.dateStartField}`] = start_date_formatted ||  false;
        }
        if (self.model.metaData?.dateStopField) {
            context[`default_${self.model.metaData.dateStopField}`] = end_date_formatted  ||  false;
        }

        self.dialog.add(FormViewDialog, {
            resModel: self.model.metaData.resModel,            
            context: context,
            onRecordSaved: async () => {
                self.onRecordSaved();                
            }
        });
    }

    onClicktimeFrame(ev){
        var target = ev.target;
        var timeFrame = target.dataset.timeframe;

        if (timeFrame === 'Quarter Day'){
            this.state.timeFrame = 'Quarter Day';
            this.model.timeFrame = 'Quarter Day';
        }
        else if (timeFrame === 'Half Day'){
            this.state.timeFrame = 'Half Day';
            this.model.timeFrame = 'Half Day';
        }
        else if (timeFrame === 'Day'){
            this.state.timeFrame = 'Day';
            this.model.timeFrame = 'Day';
        }
        else if (timeFrame === 'Week'){
            this.state.timeFrame = 'Week';
            this.model.timeFrame = 'Week';
        }
        else if (timeFrame === 'Month'){
            this.state.timeFrame = 'Month';
            this.model.timeFrame = 'Month';
        }
        this.setTimeFrame(timeFrame);
    }

    setTimeFrame(timeFrame) {
        this.env.bus.trigger("update-timeframe-basegantt", { timeFrame });
    }

    async onRecordSaved(record) {
        this.env.bus.trigger("render-basegantt");
    }
}

BaseGanttController.template = "web_base_project_gantt_view.Contoller";
BaseGanttController.components = {
    Layout,
    SearchBar,
};

BaseGanttController.props = {
    ...standardViewProps,
    Model: Function,
    modelParams: Object,
    Renderer: Function,
    buttonTemplate: String,
};
