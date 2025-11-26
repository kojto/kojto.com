/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { Component, onMounted, useRef, useState} from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import {formatDateTime, deserializeDateTime } from "@web/core/l10n/dates";

export class BaseGanttRenderer extends Component {
    setup() {
        this.viewContainerRef = useRef("viewContainer");
        this.dialog = useService('dialog');
        this.orm = useService("orm");
        
        this.state = useState({
            gantt: false,
            records: [],
        });

        useBus(this.env.bus, "render-basegantt", this.renderGantt.bind(this));
        useBus(this.env.bus, "update-timeframe-basegantt", this.renderGantt.bind(this));

        onMounted(() => {
            this.renderGantt();
        });
    }
    async renderGantt(){
        var self = this;    
        self.viewContainerRef.el.innerHTML = '';
        
        var data = await this.props.model.fetchData();
        self.state.records = data.records;

        if(self.state.records.length > 0){
            self.buildGantt();
        }
        else if (self.state.records.length == 0) {
            $(self.viewContainerRef.el).append(_t(
                `<div class="o_list_view">
                    <div class="o_view_nocontent">
                        <div class="o_nocontent_help">
                            <p class="o_view_nocontent_smiling_face">No record found. Let's create a new Task!</p>
                            <p>Click to add a new record.</p>
                        </div>
                    </div>
                </div>`
            ));
            return;
        };
    }

    buildGantt(){
        var self = this;
        self.state.gantt = new Gantt(self.viewContainerRef.el, self.state.records, {
            view_mode: self.props.model.timeFrame,
            header_height: 50,
            column_width: 30,
            step: 24,
            view_modes: ['Quarter Day', 'Half Day', 'Day', 'Week', 'Month'],
            bar_height: 20,
            bar_corner_radius: 3,
            arrow_curve: 5,
            padding: 18, 
            date_format: 'YYYY-MM-DD',

            custom_popup_html:  function(task) {            
                const users_names = task.users_names ? task.users_names : '';
                return `
                    <div class="details-container" style="opacity: 1; width: 200px; left: auto; top: auto;">
                        <div class="title">${task.name}</div>
                        <div class="subtitle">                                
                            Start: ${task.start} <br/> 
                            Stop: ${task.end} <br/>
                            Assigned to: ${users_names} <br/>
                            Task Progress: ${task.progress ? task.progress : ''} <br/>
                        </div>
                    </div>
                `;
            },                

            on_date_change: function(task, start, end) {
                var start = new Date(start).toISOString().slice(0, 10).replace(/T|Z/g, ' ');
                var end = new Date(end).toISOString().slice(0, 10).replace(/T|Z/g, ' ');
                
                var dates = {};
                
                var start_date = formatDateTime(deserializeDateTime(start), {
                    format: "yyyy-MM-dd HH:mm:ss",
                    numberingSystem: "latn",
                })
                var end_date = formatDateTime(deserializeDateTime(end), {
                    format: "yyyy-MM-dd HH:mm:ss",
                    numberingSystem: "latn",
                })


                dates[self.props.model.metaData.dateStartField] = start_date;
                dates[self.props.model.metaData.dateStopField] = end_date;

                self.orm.call(self.props.model.metaData.resModel, "write", [
                    [parseInt(task.id, 10)],
                    dates
                ]);
            },

            on_click: function (task) {
                self.dialog.add(FormViewDialog, {
                    resModel: self.props.model.metaData.resModel,
                    resId: parseInt(task.id),
                    context: session.user_context,
                    onRecordSaved: async () => {
                        self.renderGantt();
                    }
                });                
            },

            on_progress_change: function(task, progress) {
                if (self.props.model.metaData.taskProgress){
                    var data = {}
                    data[self.props.model.metaData.taskProgress] = progress;
                    self.orm.call(self.props.model.metaData.resModel, "write", [
                        [parseInt(task.id, 10)],
                        data
                    ]);
                }                      
            },

            on_view_change: function(mode) {

            },
        
        });
    }
}

BaseGanttRenderer.template = "web_base_project_gantt_view.ViewRenderer";
BaseGanttRenderer.props = {
    model: { type: Object },
};
